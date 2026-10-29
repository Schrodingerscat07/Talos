#include "ResearchEnvironment.h"
#include "ResearchMotorAnim.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Dom/JsonObject.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"

namespace
{
FQuat LocalRotation(USkeletalMeshComponent* Mesh, int32 Index)
{
    const int32 Parent = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton().GetParentIndex(Index);
    const FTransform Bone = Mesh->GetBoneTransform(Index);
    return Parent == INDEX_NONE ? Bone.GetRotation() : Bone.GetRelativeTransform(Mesh->GetBoneTransform(Parent)).GetRotation();
}
TArray<TSharedPtr<FJsonValue>> QuatArray(const FQuat& Q)
{
    return {MakeShared<FJsonValueNumber>(Q.X), MakeShared<FJsonValueNumber>(Q.Y), MakeShared<FJsonValueNumber>(Q.Z), MakeShared<FJsonValueNumber>(Q.W)};
}
}

void AResearchEnvironment::SetupMotor()
{
    FString Path;
    bMotorRequested = FParse::Value(FCommandLine::Get(), TEXT("ERLMotorMap="), Path);
    if (!bMotorRequested) return;
    MotorError = TEXT("invalid_motor_mapping");
    FString Text, Format, Component;
    if (!FFileHelper::LoadFileToString(Text, *Path) || Text.Len() > 65536 ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), MotorMapping) || !MotorMapping ||
        MotorMapping->Values.Num()!=3 || !MotorMapping->TryGetStringField(TEXT("format"), Format) || Format!=TEXT("talos-motor-map/1.0") ||
        !MotorMapping->TryGetStringField(TEXT("body_component"), Component)) return;
    if (!AnimatedBody || Component!=AnimatedBody->GetName() || Profile.AnimationMode!=TEXT("clips") || Locomotion.Num()!=5 || Locomotion.Contains(nullptr))
    { MotorError=TEXT("motor_requires_selected_body_and_compatible_clips"); return; }
    const TArray<TSharedPtr<FJsonValue>>* Entries=nullptr;
    if (!MotorMapping->TryGetArrayField(TEXT("channels"), Entries) || Entries->Num()<1 || Entries->Num()>64) return;
    TArray<FResearchMotorChannel> Channels;
    TSet<FString> Names; TSet<FName> Bones;
    for (const auto& Entry : *Entries)
    {
        if (Entry->Type!=EJson::Object) return;
        auto O=Entry->AsObject(); FResearchMotorChannel C; FString Bone;
        const TArray<TSharedPtr<FJsonValue>>* Axis=nullptr;
        if (O->Values.Num()!=5 || !O->TryGetStringField(TEXT("name"),C.Name) || C.Name.IsEmpty() || Names.Contains(C.Name) ||
            !O->TryGetStringField(TEXT("bone"),Bone) || !O->TryGetArrayField(TEXT("axis"),Axis) || Axis->Num()!=3 ||
            !O->HasTypedField<EJson::Number>(TEXT("limit_deg")) || !O->TryGetNumberField(TEXT("limit_deg"),C.Limit) ||
            !O->HasTypedField<EJson::Number>(TEXT("rate_deg_s")) || !O->TryGetNumberField(TEXT("rate_deg_s"),C.Rate) ||
            !FMath::IsFinite(C.Limit) || C.Limit<=0 || C.Limit>90 || !FMath::IsFinite(C.Rate) || C.Rate<=0 || C.Rate>360) return;
        for(int32 I=0;I<3;++I) {double V; if((*Axis)[I]->Type!=EJson::Number || !(*Axis)[I]->TryGetNumber(V) || !FMath::IsFinite(V)) return; C.Axis[I]=V;}
        if (!FMath::IsNearlyEqual(C.Axis.SizeSquared(),1.0,0.0001)) return;
        C.Bone=FName(*Bone); C.MeshIndex=AnimatedBody->GetBoneIndex(C.Bone);
        if(C.MeshIndex==INDEX_NONE || Bones.Contains(C.Bone)) {MotorError=TEXT("missing_or_duplicate_motor_bone");return;}
        Names.Add(C.Name); Bones.Add(C.Bone); Channels.Add(C);
    }
    // Pin the diagnostic to LOD0 so configured finger bones cannot be dropped by
    // distance-dependent LOD selection. Other LODs require separate validation.
    AnimatedBody->SetForcedLOD(1);
    AnimatedBody->SetAnimInstanceClass(UResearchMotorAnim::StaticClass());
    MotorAnim=Cast<UResearchMotorAnim>(AnimatedBody->GetAnimInstance());
    if(!MotorAnim) {MotorError=TEXT("motor_anim_instance_failed");return;}
    MotorAnim->Channels=Channels;
    UpdateAnimation();
    for(const auto& C:Channels) MotorNeutral.Add(LocalRotation(AnimatedBody,C.MeshIndex));
    MotorError.Empty();
}

TSharedRef<FJsonObject> AResearchEnvironment::DescribeMotor() const
{
    auto D=MakeShared<FJsonObject>();
    D->SetStringField(TEXT("protocol"),TEXT("erl/1.0"));
    D->SetStringField(TEXT("format"),TEXT("talos-motor-state/1.0"));
    D->SetBoolField(TEXT("enabled"),bMotorRequested);
    D->SetBoolField(TEXT("ready"),MotorAnim && MotorError.IsEmpty());
    D->SetStringField(TEXT("error"),MotorError);
    D->SetStringField(TEXT("mode"),TEXT("local_axis_offsets_over_frozen_supplied_idle_before_post_process"));
    D->SetStringField(TEXT("scope"),TEXT("privileged_motor_diagnostic_not_policy_sensor"));
    D->SetNumberField(TEXT("forced_lod"),0);
    D->SetStringField(TEXT("episode_id"),Episode); D->SetNumberField(TEXT("step_index"),StepIndex);
    if(MotorMapping) D->SetObjectField(TEXT("mapping"),MotorMapping);
    TArray<TSharedPtr<FJsonValue>> Values;
    if(MotorAnim) for(int32 I=0;I<MotorAnim->Channels.Num();++I)
    {
        const auto& C=MotorAnim->Channels[I]; auto O=MakeShared<FJsonObject>();
        O->SetStringField(TEXT("name"),C.Name); O->SetStringField(TEXT("bone"),C.Bone.ToString());
        O->SetNumberField(TEXT("requested_deg"),C.Degrees);
        const FQuat Actual=LocalRotation(AnimatedBody,C.MeshIndex);
        O->SetArrayField(TEXT("evaluated_local_quat_xyzw"),QuatArray(Actual));
        if(MotorNeutral.IsValidIndex(I))
        {
            const FQuat Delta=(MotorNeutral[I].Inverse()*Actual).GetNormalized();
            O->SetArrayField(TEXT("neutral_local_quat_xyzw"),QuatArray(MotorNeutral[I]));
            O->SetNumberField(TEXT("measured_axis_delta_deg"),FRotator::NormalizeAxis(FMath::RadiansToDegrees(2*FMath::Atan2(FVector(Delta.X,Delta.Y,Delta.Z)|C.Axis,Delta.W))));
        }
        Values.Add(MakeShared<FJsonValueObject>(O));
    }
    D->SetArrayField(TEXT("channels"),Values); return D;
}

bool AResearchEnvironment::ApplyMotor(const TSharedPtr<FJsonObject>& Data, FString& Error, int32& Code)
{
    Code=400; Error=TEXT("invalid_motor_command");
    if(!MotorAnim || !MotorError.IsEmpty()) {Code=503;Error=TEXT("motor_not_ready");return false;}
    FString Format, ExpectedEpisode; double ExpectedStep;
    const TSharedPtr<FJsonObject>* Targets=nullptr;
    if(Data->Values.Num()!=4 || !Data->TryGetStringField(TEXT("format"),Format) || Format!=TEXT("talos-motor-command/1.0") ||
       !Data->TryGetStringField(TEXT("episode_id"),ExpectedEpisode) || !Data->HasTypedField<EJson::Number>(TEXT("expected_step")) ||
       !Data->TryGetNumberField(TEXT("expected_step"),ExpectedStep) || !FMath::IsFinite(ExpectedStep) ||
       !Data->TryGetObjectField(TEXT("targets_deg"),Targets) || (*Targets)->Values.Num()!=MotorAnim->Channels.Num()) return false;
    TArray<double> Values;
    for(const auto& C:MotorAnim->Channels)
    {
        double V;
        if(!(*Targets)->HasTypedField<EJson::Number>(C.Name) || !(*Targets)->TryGetNumberField(C.Name,V) || !FMath::IsFinite(V) || FMath::Abs(V)>C.Limit) return false;
        if(FMath::Abs(V-C.Degrees)>C.Rate*StepSeconds+0.00001) {Error=TEXT("motor_rate_limit_exceeded");return false;}
        Values.Add(V);
    }
    if(ExpectedEpisode!=Episode || ExpectedStep!=StepIndex || StepIndex>=MaxSteps) {Code=409;Error=TEXT("episode_or_step_conflict");return false;}
    // Commit only after all channels and ordering constraints have passed.
    for(int32 I=0;I<Values.Num();++I) MotorAnim->Channels[I].Degrees=Values[I];
    LastVelocity=FVector::ZeroVector; bBlocked=false; LastHitActor.Empty(); ++StepIndex;
    UpdateAnimation(); return true;
}
