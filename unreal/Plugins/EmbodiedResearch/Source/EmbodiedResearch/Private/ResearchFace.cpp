#include "ResearchEnvironment.h"
#include "ResearchFaceAnim.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/Skeleton.h"
#include "Dom/JsonObject.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"

void AResearchEnvironment::SetupFace()
{
    FString Path; bFaceRequested=FParse::Value(FCommandLine::Get(),TEXT("ERLFaceMap="),Path);
    if(!bFaceRequested)return;
    FaceError=TEXT("invalid_face_mapping");
    if((bMotorRequested && (!MotorAnim || !MotorError.IsEmpty())) || !AnimatedBody || Locomotion.Num()!=5 || Locomotion.Contains(nullptr)) {FaceError=TEXT("face_requires_exclusive_clip_instance");return;}
    FString Text,Format,Component;
    if(!FFileHelper::LoadFileToString(Text,*Path) || Text.Len()>16384 ||
       !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),FaceMapping) || !FaceMapping || FaceMapping->Values.Num()!=3 ||
       !FaceMapping->TryGetStringField(TEXT("format"),Format) || Format!=TEXT("talos-face-map/1.0") || !FaceMapping->TryGetStringField(TEXT("component"),Component))return;
    TArray<USkeletalMeshComponent*> Meshes;Avatar->GetComponents(Meshes);
    for(auto* Mesh:Meshes) if(Mesh->GetName()==Component)ControlledFace=Mesh;
    if(!ControlledFace || !ControlledFace->GetSkeletalMeshAsset() || ControlledFace->GetAttachParent()!=AnimatedBody || !ControlledFace->GetPostProcessInstance())
    {FaceError=TEXT("face_requires_body_parent_and_existing_post_process");return;}
    TArray<FName> Available; ControlledFace->GetSkeletalMeshAsset()->GetSkeleton()->GetCurveMetaDataNames(Available);
    const TArray<TSharedPtr<FJsonValue>>* Entries=nullptr;
    if(!FaceMapping->TryGetArrayField(TEXT("channels"),Entries) || Entries->Num()<1 || Entries->Num()>32)return;
    TArray<FResearchFaceChannel> Channels;TSet<FString> Names;TSet<FName> Curves;
    for(const auto& V:*Entries)
    {
        if(V->Type!=EJson::Object)return;
        const auto O=V->AsObject();FResearchFaceChannel C;FString Curve;
        if(O->Values.Num()!=2 || !O->TryGetStringField(TEXT("name"),C.Name) || C.Name.IsEmpty() || Names.Contains(C.Name) || !O->TryGetStringField(TEXT("curve"),Curve))return;
        C.Curve=FName(*Curve);
        if(!Available.Contains(C.Curve) || Curves.Contains(C.Curve)) {FaceError=TEXT("missing_or_duplicate_face_curve");return;}
        Names.Add(C.Name);Curves.Add(C.Curve);Channels.Add(C);
    }
    ControlledFace->SetForcedLOD(1);
    ControlledFace->SetAnimInstanceClass(UResearchFaceAnim::StaticClass());
    FaceAnim=Cast<UResearchFaceAnim>(ControlledFace->GetAnimInstance());
    if(!FaceAnim || !ControlledFace->GetPostProcessInstance()) {FaceError=TEXT("face_instance_or_post_process_failed");return;}
    FaceAnim->Channels=Channels;
    ControlledFace->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    ControlledFace->SetComponentTickEnabled(false);
    UpdateAnimation();
    // Supplied review lighting, only in an explicitly face-controlled instance.
    // Front fills illuminate the eye sockets without adding shadow-map cost.
    for(int32 I=0; I<2; ++I)
    {
        const FRotator Rotation(-10,GetActorRotation().Yaw+180+(I==0 ? -25 : 25),0);
        auto* Fill=GetWorld()->SpawnActor<ADirectionalLight>(Avatar->GetActorLocation(),Rotation);
        if(!Fill) {FaceError=TEXT("face_review_light_failed");return;}
        Fill->GetComponent()->SetIntensity(I==0 ? 3.0f : 1.5f);
        Fill->GetComponent()->SetCastShadows(false);
        Fill->AttachToActor(this,FAttachmentTransformRules::KeepWorldTransform);
    }
    FaceError.Empty();
}

TSharedRef<FJsonObject> AResearchEnvironment::DescribeFace() const
{
    auto D=MakeShared<FJsonObject>();D->SetStringField(TEXT("protocol"),TEXT("erl/1.0"));D->SetStringField(TEXT("format"),TEXT("talos-face-state/1.0"));
    D->SetBoolField(TEXT("enabled"),bFaceRequested);D->SetBoolField(TEXT("ready"),FaceAnim && FaceError.IsEmpty());D->SetStringField(TEXT("error"),FaceError);
    D->SetStringField(TEXT("scope"),TEXT("privileged_face_diagnostic_curve_values_are_not_geometry_measurements"));
    D->SetStringField(TEXT("episode_id"),Episode);D->SetNumberField(TEXT("step_index"),StepIndex);
    D->SetNumberField(TEXT("rate_per_second"),2);D->SetNumberField(TEXT("forced_lod"),0);
    if(FaceAnim && FaceError.IsEmpty())
        D->SetStringField(TEXT("review_lighting"),TEXT("front_unshadowed_directional_fills_v1: pitch=-10 yaw=agent+155/205 intensity=3/1.5; affects_all_captures"));
    if(FaceMapping)D->SetObjectField(TEXT("mapping"),FaceMapping);
    if(ControlledFace && ControlledFace->GetPostProcessInstance())D->SetStringField(TEXT("post_process_class"),ControlledFace->GetPostProcessInstance()->GetClass()->GetPathName());
    TArray<TSharedPtr<FJsonValue>> Values;
    if(FaceAnim)for(const auto& C:FaceAnim->Channels)
    {
        auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("name"),C.Name);O->SetStringField(TEXT("curve"),C.Curve.ToString());
        O->SetNumberField(TEXT("requested"),C.Value);O->SetNumberField(TEXT("evaluated_curve"),FaceAnim->GetCurveValue(C.Curve));Values.Add(MakeShared<FJsonValueObject>(O));
    }
    D->SetArrayField(TEXT("channels"),Values);return D;
}

bool AResearchEnvironment::ApplyFace(const TSharedPtr<FJsonObject>& Data,FString& Error,int32& Code, bool bValidateOnly)
{
    Code=400;Error=TEXT("invalid_face_command");
    if(!FaceAnim || !FaceError.IsEmpty()){Code=503;Error=TEXT("face_not_ready");return false;}
    FString Format,ExpectedEpisode;double ExpectedStep;const TSharedPtr<FJsonObject>* Targets=nullptr;
    if(Data->Values.Num()!=4 || !Data->TryGetStringField(TEXT("format"),Format) || Format!=TEXT("talos-face-command/1.0") ||
       !Data->TryGetStringField(TEXT("episode_id"),ExpectedEpisode) || !Data->HasTypedField<EJson::Number>(TEXT("expected_step")) ||
       !Data->TryGetNumberField(TEXT("expected_step"),ExpectedStep) || !FMath::IsFinite(ExpectedStep) ||
       !Data->TryGetObjectField(TEXT("targets"),Targets) || (*Targets)->Values.Num()!=FaceAnim->Channels.Num())return false;
    TArray<double> Values;
    for(const auto& C:FaceAnim->Channels)
    {
        double V;
        if(!(*Targets)->HasTypedField<EJson::Number>(C.Name) || !(*Targets)->TryGetNumberField(C.Name,V) || !FMath::IsFinite(V) || V<0 || V>1)return false;
        if(FMath::Abs(V-C.Value)>2*StepSeconds+0.00001){Error=TEXT("face_rate_limit_exceeded");return false;}
        Values.Add(V);
    }
    if(ExpectedEpisode!=Episode || ExpectedStep!=StepIndex || StepIndex>=MaxSteps){Code=409;Error=TEXT("episode_or_step_conflict");return false;}
    if(bValidateOnly)return true;
    for(int32 I=0;I<Values.Num();++I)FaceAnim->Channels[I].Value=Values[I];
    LastVelocity=FVector::ZeroVector;bBlocked=false;LastHitActor.Empty();++StepIndex;UpdateAnimation();return true;
}
