#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Plain data only; no UObjects or avatar-specific dependencies.
struct FResearchProfile
{
    bool bProvided=false;
    FString Id,Kind=TEXT("home"),Map=TEXT("/Engine/Maps/Entry");
    FString AvatarKind=TEXT("blueprint"),AvatarAsset,BodyComponent=TEXT("Body"),AnimationMode=TEXT("clips");
    FString SnapshotPath;
    TSharedPtr<FJsonObject> Document;
    FVector Spawn=FVector(-600,-130,89),Offset=FVector(0,0,-88),Scale=FVector::OneVector,EyeOffset=FVector(10,0,77),Overview=FVector(-1800,2600,2600);
    TArray<double> Bounds={-1400,-1250,2800,2500};
    TArray<FString> Clips;
    float Radius=34,HalfHeight=88,Yaw=-90,Heading=0,Speed=150,TurnRate=90,LookRate=60,EyeExposure=-4,ObserverExposure=-2;
    int32 MaxSteps=500;
    bool bDisableGroom=true;
    static bool Load(FResearchProfile& Out,FString& Error);
};
