#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "ResearchMotorAnim.generated.h"

// Transient per-instance bindings; never written into the source avatar asset.
struct FResearchMotorChannel
{
    FString Name;
    FName Bone;
    int32 MeshIndex = INDEX_NONE;
    FVector Axis = FVector::ZAxisVector;
    double Limit = 30;
    double Rate = 120;
    double Degrees = 0;
};

UCLASS(Transient)
class EMBODIEDRESEARCH_API UResearchMotorAnim : public UAnimSingleNodeInstance
{
    GENERATED_BODY()
public:
    TArray<FResearchMotorChannel> Channels;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};
