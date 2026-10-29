#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "HttpRouteHandle.h"
#include "HttpServerRequest.h"
#include "HttpResultCallback.h"
#include "ResearchProfile.h"
#include "ResearchEnvironment.generated.h"

class UCapsuleComponent;
class USceneCaptureComponent2D;
class UTextureRenderTarget2D;
class UCameraComponent;
class IHttpRouter;
class FJsonObject;
class UInstancedStaticMeshComponent;
class USkeletalMeshComponent;
class UAnimSequence;
class UResearchMotorAnim;

UCLASS()
class EMBODIEDRESEARCH_API AResearchEnvironment : public AActor
{
    GENERATED_BODY()
public:
    AResearchEnvironment();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    UPROPERTY() TObjectPtr<UCapsuleComponent> Body;
    UPROPERTY() TObjectPtr<USceneCaptureComponent2D> Eye;
    UPROPERTY() TObjectPtr<UTextureRenderTarget2D> Image;
    UPROPERTY() TObjectPtr<USceneCaptureComponent2D> ObserverEye;
    UPROPERTY() TObjectPtr<UTextureRenderTarget2D> ObserverImage;
    UPROPERTY() TObjectPtr<UCameraComponent> Observer;
    UPROPERTY() TObjectPtr<AActor> Avatar;
    UPROPERTY() TObjectPtr<AActor> Obstacle;
    UPROPERTY() TObjectPtr<AActor> WorldGeometry;
    UPROPERTY() TMap<FString,TObjectPtr<UInstancedStaticMeshComponent>> Pieces;
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> AnimatedBody;
    UPROPERTY() TArray<TObjectPtr<UAnimSequence>> Locomotion;
    UPROPERTY() TObjectPtr<UResearchMotorAnim> MotorAnim;
    TSharedPtr<FJsonObject> MotorMapping;
    FString MotorError;
    TArray<FQuat> MotorNeutral;
    bool bMotorRequested = false;
    void SetupMotor();
    TSharedRef<FJsonObject> DescribeMotor() const;
    bool ApplyMotor(const TSharedPtr<FJsonObject>& Data, FString& Error, int32& Code);
    FString WorldName = TEXT("home");
    FString AnimationState = TEXT("unavailable");
    float GaitPhase = 0;
    void CreateHome();
    void CreateLayout();
    void CreateDaylight();
    void Piece(const FVector& Position, const FVector& Size, const FString& Material, const FString& Shape = TEXT("Cube"), const FRotator& Rotation = FRotator::ZeroRotator, bool bCollision = true);
    void SetupAnimation();
    void UpdateAnimation();
    TSharedPtr<IHttpRouter> Router;
    TArray<FHttpRouteHandle> Routes;
    FString Token;
    FString AvatarPath;
    FString Episode;
    FString LastHitActor;
    int32 Seed = 0;
    int32 StepIndex = 0;
    int32 MaxSteps = 500;
    bool bBlocked = false;
    bool bAvatarLoaded = false;
    bool bRGB = true;
    bool bCapturePending = false;
    void ReplyAfterPose(const FHttpResultCallback& Complete);
    float Heading = 0;
    FResearchProfile Profile;
    float Pitch = 0;
    FVector LastVelocity = FVector::ZeroVector;
    static constexpr double StepSeconds = 0.1;
    void CreateRoom();
    AActor* AddBlock(const FVector& Position, const FVector& Size, const FString& Label);
    void ResetState(int32 InSeed);
    TSharedRef<FJsonObject> Describe() const;
    TSharedRef<FJsonObject> DescribeRig() const;
    TSharedRef<FJsonObject> Observe();
    bool Handle(const FHttpServerRequest& Request, const FHttpResultCallback& Complete, const FString& Operation);
};

UCLASS()
class EMBODIEDRESEARCH_API UResearchWorldSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
protected:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;
};
