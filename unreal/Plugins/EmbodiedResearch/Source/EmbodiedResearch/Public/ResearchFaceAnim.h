#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "ResearchFaceAnim.generated.h"

struct FResearchFaceChannel
{
    FString Name;
    FName Curve;
    float Value=0;
};

UCLASS(Transient)
class EMBODIEDRESEARCH_API UResearchFaceAnim : public UAnimInstance
{
    GENERATED_BODY()
public:
    TArray<FResearchFaceChannel> Channels;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};
