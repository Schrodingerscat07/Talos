#include "ResearchEnvironment.h"
#include "ResearchMotorAnim.h"
#include "ResearchFaceAnim.h"
#include "Dom/JsonObject.h"

TSharedRef<FJsonObject> AResearchEnvironment::DescribeControl() const
{
    auto D=MakeShared<FJsonObject>();
    D->SetStringField(TEXT("protocol"),TEXT("erl/1.0"));
    D->SetStringField(TEXT("format"),TEXT("talos-control-state/1.0"));
    D->SetBoolField(TEXT("ready"),bMotorRequested && bFaceRequested && MotorAnim && FaceAnim && MotorError.IsEmpty() && FaceError.IsEmpty());
    D->SetStringField(TEXT("episode_id"),Episode);D->SetNumberField(TEXT("step_index"),StepIndex);
    D->SetObjectField(TEXT("motor"),DescribeMotor());D->SetObjectField(TEXT("face"),DescribeFace());
    D->SetStringField(TEXT("scope"),TEXT("privileged_combined_pose_diagnostic"));return D;
}

bool AResearchEnvironment::ApplyControl(const TSharedPtr<FJsonObject>& Data,FString& Error,int32& Code)
{
    Code=400;Error=TEXT("invalid_control_command");
    if(!bMotorRequested || !bFaceRequested || !MotorAnim || !FaceAnim || !MotorError.IsEmpty() || !FaceError.IsEmpty())
    {Code=503;Error=TEXT("combined_control_not_ready");return false;}
    FString Format;const TSharedPtr<FJsonObject>* BodyTargets=nullptr;const TSharedPtr<FJsonObject>* FaceTargets=nullptr;
    if(Data->Values.Num()!=5 || !Data->TryGetStringField(TEXT("format"),Format) || Format!=TEXT("talos-control-command/1.0") ||
       !Data->HasField(TEXT("episode_id")) || !Data->HasField(TEXT("expected_step")) ||
       !Data->TryGetObjectField(TEXT("motor_targets_deg"),BodyTargets) || !Data->TryGetObjectField(TEXT("face_targets"),FaceTargets))return false;
    auto Motor=MakeShared<FJsonObject>();auto Face=MakeShared<FJsonObject>();
    for(const TCHAR* Key:{TEXT("episode_id"),TEXT("expected_step")})
    {Motor->SetField(Key,Data->TryGetField(Key));Face->SetField(Key,Data->TryGetField(Key));}
    Motor->SetStringField(TEXT("format"),TEXT("talos-motor-command/1.0"));Motor->SetObjectField(TEXT("targets_deg"),*BodyTargets);
    Face->SetStringField(TEXT("format"),TEXT("talos-face-command/1.0"));Face->SetObjectField(TEXT("targets"),*FaceTargets);
    // Both validators are read-only here. No pose, clock or animation change on failure.
    if(!ApplyMotor(Motor,Error,Code,true) || !ApplyFace(Face,Error,Code,true))return false;
    for(auto& C:MotorAnim->Channels) C.Degrees=(*BodyTargets)->GetNumberField(C.Name);
    for(auto& C:FaceAnim->Channels) C.Value=(*FaceTargets)->GetNumberField(C.Name);
    LastVelocity=FVector::ZeroVector;bBlocked=false;LastHitActor.Empty();++StepIndex;
    UpdateAnimation();return true;
}
