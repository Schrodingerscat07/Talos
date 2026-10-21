#include "ResearchEnvironment.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "GameFramework/MovementComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Components/PointLightComponent.h"
#include "Engine/PointLight.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "TimerManager.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "HttpServerModule.h"
#include "HttpServerResponse.h"
#include "IHttpRouter.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Misc/Base64.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/FileHelper.h"
#include "Misc/EngineVersion.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/PackageName.h"
#include "ImageUtils.h"
#include "RHI.h"

namespace
{
TArray<TSharedPtr<FJsonValue>> Vec(const FVector& V)
{
    return {MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z)};
}
void Reply(const FHttpResultCallback& Complete, const TSharedRef<FJsonObject>& Data, int32 Code = 200)
{
    FString Text;
    FJsonSerializer::Serialize(Data, TJsonWriterFactory<>::Create(&Text));
    auto Response = FHttpServerResponse::Create(Text, TEXT("application/json"));
    Response->Code = static_cast<EHttpServerResponseCodes>(Code);
    Response->Headers.Add(TEXT("Cache-Control"), {TEXT("no-store")});
    Complete(MoveTemp(Response));
}
void Fail(const FHttpResultCallback& Complete, int32 Code, const FString& Message)
{
    auto Data = MakeShared<FJsonObject>();
    Data->SetStringField(TEXT("error"), Message);
    Reply(Complete, Data, Code);
}
}

AResearchEnvironment::AResearchEnvironment()
{
    PrimaryActorTick.bCanEverTick = false;
    Body = CreateDefaultSubobject<UCapsuleComponent>(TEXT("ResearchBody"));
    Body->InitCapsuleSize(34, 88);
    Body->SetCollisionProfileName(TEXT("Pawn"));
    RootComponent = Body;
    Eye = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("AgentEye"));
    Eye->SetupAttachment(Body);
    Eye->SetRelativeLocation(FVector(10, 0, 77));
    Eye->bCaptureEveryFrame = false;
    Eye->bCaptureOnMovement = false;
    Eye->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
    Eye->FOVAngle = 90;
    Observer = CreateDefaultSubobject<UCameraComponent>(TEXT("ResearchObserver"));
    Observer->SetupAttachment(Body);
    Observer->SetRelativeLocation(FVector(220, -220, 120));
    Observer->SetRelativeRotation(FRotator(-21, 135, 0));
    ObserverEye = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("ObserverCapture"));
    ObserverEye->SetupAttachment(Observer);
    ObserverEye->bCaptureEveryFrame = false;
    ObserverEye->bCaptureOnMovement = false;
    ObserverEye->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
    ObserverEye->FOVAngle = 60;
    for (auto* Capture : {Eye.Get(),ObserverEye.Get()})
    {
        Capture->PostProcessSettings.bOverride_AutoExposureMethod = true;
        Capture->PostProcessSettings.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
        Capture->PostProcessSettings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
        Capture->PostProcessSettings.AutoExposureApplyPhysicalCameraExposure = false;
        Capture->PostProcessSettings.bOverride_AutoExposureBias = true;
        Capture->PostProcessSettings.AutoExposureBias = 0;
    }
}

AActor* AResearchEnvironment::AddBlock(const FVector& Position, const FVector& Size, const FString& Label)
{
    auto* Block = GetWorld()->SpawnActor<AStaticMeshActor>(Position, FRotator::ZeroRotator);
    auto* Mesh = Block->GetStaticMeshComponent();
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
    Mesh->SetWorldScale3D(Size / 100.0);
    Mesh->SetCollisionProfileName(TEXT("BlockAll"));
    Block->Tags.Add(FName(*Label));
    return Block;
}

void AResearchEnvironment::CreateRoom()
{
    AddBlock(FVector(0,0,-20), FVector(1200,1200,40), TEXT("floor"));
    AddBlock(FVector(600,0,150), FVector(30,1200,300), TEXT("east_wall"));
    AddBlock(FVector(-600,0,150), FVector(30,1200,300), TEXT("west_wall"));
    AddBlock(FVector(0,600,150), FVector(1200,30,300), TEXT("north_wall"));
    AddBlock(FVector(0,-600,150), FVector(1200,30,300), TEXT("south_wall"));
    Obstacle = AddBlock(FVector(220,150,60), FVector(100,100,120), TEXT("seeded_obstacle"));
    for (int32 I=0; I<4; ++I)
    {
        auto* Fill = GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,400),FRotator(-45,45+90*I,0));
        Fill->GetComponent()->SetIntensity(0.75f);
        Fill->GetComponent()->SetCastShadows(false);
    }
    for (const FVector P : {FVector(-250,-200,290), FVector(250,200,290)})
    {
        auto* Light = GetWorld()->SpawnActor<APointLight>(P, FRotator::ZeroRotator);
        Light->PointLightComponent->SetIntensity(15000);
        Light->PointLightComponent->SetAttenuationRadius(1600);
        Light->PointLightComponent->SetCastShadows(false);
    }
}

void AResearchEnvironment::BeginPlay()
{
    Super::BeginPlay();
    FString TokenFile;
    if (!FParse::Value(FCommandLine::Get(), TEXT("ERLTokenFile="), TokenFile) ||
        !FFileHelper::LoadFileToString(Token, *TokenFile) || Token.TrimStartAndEnd().Len() < 24)
    {
        UE_LOG(LogTemp, Error, TEXT("ERL: a token file with at least 24 characters is required"));
        return;
    }
    Token.TrimStartAndEndInline();
    FString ConfigError;
    if(!FResearchProfile::Load(Profile,ConfigError)) {UE_LOG(LogTemp,Error,TEXT("ERL: %s"),*ConfigError);return;}
    AvatarPath = TEXT("/Game/MetaHumans/bob/BP_bob.BP_bob_C");
    FParse::Value(FCommandLine::Get(), TEXT("ERLAvatar="), AvatarPath);
    bRGB = !FParse::Param(FCommandLine::Get(), TEXT("NullRHI"));
    float EyeExposureBias = -4;
    FParse::Value(FCommandLine::Get(),TEXT("ERLEyeExposureBias="),EyeExposureBias);
    Eye->PostProcessSettings.AutoExposureBias = FMath::IsFinite(EyeExposureBias) ? FMath::Clamp(EyeExposureBias,-8.0f,8.0f) : -4.0f;
    FParse::Value(FCommandLine::Get(),TEXT("ERLWorld="),WorldName);
    if(Profile.bProvided)
    {
        WorldName=Profile.Kind;AvatarPath=Profile.AvatarAsset;MaxSteps=Profile.MaxSteps;
        Body->SetCapsuleSize(Profile.Radius,Profile.HalfHeight);
        Eye->SetRelativeLocation(Profile.EyeOffset);
        Eye->PostProcessSettings.AutoExposureBias=Profile.EyeExposure;
    }
    else
    {
        Profile.Kind=WorldName;
        Profile.Spawn=WorldName==TEXT("room") ? FVector(0,0,89) : FVector(-600,-130,89);
        Profile.Overview=WorldName==TEXT("room") ? FVector(850,-850,1100) : FVector(-1800,2600,2600);
    }
    if(WorldName==TEXT("room")) CreateRoom();
    else if(WorldName==TEXT("home")) CreateHome();
    else if(WorldName==TEXT("layout")) CreateLayout();
    if(WorldName!=TEXT("room")) ObserverEye->PostProcessSettings.AutoExposureBias=-2;
    if(Profile.bProvided && Profile.AvatarKind==TEXT("skeletal_mesh"))
    {
        if(auto* Asset=LoadObject<USkeletalMesh>(nullptr,*AvatarPath))
        {
            Avatar=GetWorld()->SpawnActor<AActor>();
            auto* Mesh=NewObject<USkeletalMeshComponent>(Avatar,FName(*Profile.BodyComponent));
            Avatar->SetRootComponent(Mesh);Avatar->AddInstanceComponent(Mesh);
            Mesh->SetSkeletalMeshAsset(Asset);Mesh->RegisterComponent();
        }
    }
    else if (UClass* AvatarClass = LoadClass<AActor>(nullptr, *AvatarPath))
    {
        Avatar = GetWorld()->SpawnActor<AActor>(AvatarClass, FVector::ZeroVector, FRotator::ZeroRotator);
    }
    if (Avatar)
    {
            Avatar->SetActorTickEnabled(false);
            TArray<UMovementComponent*> Movers;Avatar->GetComponents(Movers);
            for(auto* Mover:Movers) {Mover->Deactivate();Mover->SetComponentTickEnabled(false);}
            Avatar->SetActorEnableCollision(false);
            Avatar->AttachToComponent(Body, FAttachmentTransformRules::KeepRelativeTransform);
            Avatar->SetActorRelativeLocation(Profile.bProvided ? Profile.Offset : FVector(0,0,-88));
            float AvatarYaw = -90;
            FParse::Value(FCommandLine::Get(),TEXT("ERLAvatarYaw="),AvatarYaw);
            if(Profile.bProvided) AvatarYaw=Profile.Yaw;
            Avatar->SetActorRelativeRotation(FRotator(0,FMath::IsFinite(AvatarYaw) ? FRotator::NormalizeAxis(AvatarYaw) : -90,0));
            Eye->HideActorComponents(Avatar);
            bAvatarLoaded = true;
            if(Profile.bProvided) Avatar->SetActorRelativeScale3D(Profile.Scale);
    }
    if (!bAvatarLoaded) UE_LOG(LogTemp, Error, TEXT("ERL: avatar failed to load: %s"), *AvatarPath);
    SetupAnimation();
    if(Profile.bProvided) ObserverEye->PostProcessSettings.AutoExposureBias=Profile.ObserverExposure;
    if (bRGB)
    {
        Image = NewObject<UTextureRenderTarget2D>(this);
        Image->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8;
        Image->InitAutoFormat(160,120);
        Image->UpdateResourceImmediate(true);
        Eye->TextureTarget = Image;
        ObserverImage = NewObject<UTextureRenderTarget2D>(this);
        ObserverImage->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8;
        ObserverImage->InitAutoFormat(640,480);
        ObserverImage->UpdateResourceImmediate(true);
        ObserverEye->TextureTarget = ObserverImage;
    }
    ResetState(0);
    if (auto* Player = UGameplayStatics::GetPlayerController(this, 0)) Player->SetViewTarget(this);
    GetWorld()->GetTimerManager().SetTimerForNextTick([Weak=TWeakObjectPtr<AResearchEnvironment>(this)]()
    {
        if (!Weak.IsValid()) return;
        if (auto* Player = UGameplayStatics::GetPlayerController(Weak.Get(),0))
        {
            if (APawn* Pawn = Player->GetPawn())
            {
                Pawn->SetActorEnableCollision(false);
                Pawn->SetActorHiddenInGame(true);
                Weak->Body->IgnoreActorWhenMoving(Pawn,true);
            }
            Player->SetViewTarget(Weak.Get());
        }
    });
    int32 Port = 8765;
    FParse::Value(FCommandLine::Get(), TEXT("ERLPort="), Port);
    if (Port < 1024 || Port > 65535) return;
    // Configure this listener explicitly; never expose the research control endpoint to a LAN.
    GConfig->SetString(TEXT("HTTPServer.Listeners"), TEXT("DefaultBindAddress"), TEXT("127.0.0.1"), GEngineIni);
    GConfig->SetArray(TEXT("HTTPServer.Listeners"), TEXT("ListenerOverrides"),
        {FString::Printf(TEXT("(Port=%d,BindAddress=127.0.0.1)"), Port)}, GEngineIni);
    Router = FHttpServerModule::Get().GetHttpRouter(Port, true);
    if (!Router) return;
    for (const FString Op : {TEXT("health"),TEXT("spec"),TEXT("observe"),TEXT("overview"),TEXT("layout"),TEXT("reset"),TEXT("step")})
    {
        const auto Verb = (Op == TEXT("reset") || Op == TEXT("step")) ? EHttpServerRequestVerbs::VERB_POST : EHttpServerRequestVerbs::VERB_GET;
        Routes.Add(Router->BindRoute(FHttpPath(TEXT("/v1/") + Op), Verb,
            FHttpRequestHandler::CreateLambda([Weak = TWeakObjectPtr<AResearchEnvironment>(this), Op](const FHttpServerRequest& Request, const FHttpResultCallback& Complete)
            {
                if (!Weak.IsValid()) { Fail(Complete,503,TEXT("environment_unavailable")); return true; }
                return Weak->Handle(Request, Complete, Op);
            })));
    }
    FHttpServerModule::Get().StartAllListeners();
    UE_LOG(LogTemp, Display, TEXT("ERL_READY port=%d avatar_loaded=%d rgb=%d"), Port, bAvatarLoaded, bRGB);
}

void AResearchEnvironment::ResetState(int32 InSeed)
{
    Seed = InSeed;
    FRandomStream Random(Seed);
    if(Obstacle) Obstacle->SetActorLocation(WorldName==TEXT("room") ? FVector(220,Random.FRandRange(-200,200),60) : FVector(220,Random.FRandRange(100,200),35));
    SetActorLocationAndRotation(Profile.Spawn,FRotator(0,Profile.Heading,0),false,nullptr,ETeleportType::TeleportPhysics);
    Eye->SetRelativeRotation(FRotator::ZeroRotator);
    Heading=Profile.Heading;Pitch=0;
    LastVelocity = FVector::ZeroVector;
    StepIndex = 0;
    bBlocked = false;
    LastHitActor.Empty();
    Episode = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower);
    GaitPhase=0;
    UpdateAnimation();
}

TSharedRef<FJsonObject> AResearchEnvironment::Describe() const
{
    auto D = MakeShared<FJsonObject>();
    D->SetStringField(TEXT("protocol"),TEXT("erl/1.0"));
    D->SetStringField(TEXT("environment"),WorldName==TEXT("room") ? TEXT("unreal_kinematic_room_v1") : TEXT("unreal_home_courtyard_workshop_v1"));
    if(WorldName==TEXT("layout") || WorldName==TEXT("map")) D->SetStringField(TEXT("environment"),TEXT("unreal_configurable_")+WorldName+TEXT("_v1"));
    if(Profile.bProvided) D->SetObjectField(TEXT("configuration"),Profile.Document.ToSharedRef());
    D->SetStringField(TEXT("profile_id"),Profile.bProvided ? Profile.Id : TEXT("legacy_cli"));
    D->SetStringField(TEXT("reset_scope"),WorldName==TEXT("map") ? TEXT("avatar_only_static_map_required_mutable_world_needs_reset_adapter") : WorldName==TEXT("layout") ? TEXT("avatar_only_static_layout") : TEXT("avatar_and_reference_seeded_obstacle"));
    D->SetStringField(TEXT("animation"),AnimationState==TEXT("unavailable") ? TEXT("none") : TEXT("supplied_Epic_template_IK_retargeted_to_Bob_command_step_pose"));
    if(Profile.bProvided) D->SetStringField(TEXT("animation"),Profile.AnimationMode==TEXT("clips") ? TEXT("configured_supplied_animation_sequences") : Profile.AnimationMode);
    D->SetBoolField(TEXT("animation_loaded"),AnimatedBody && Locomotion.Num()==5 && !Locomotion.Contains(nullptr));
    D->SetStringField(TEXT("world_scope"),WorldName==TEXT("room") ? TEXT("phase_1_interface_room") : TEXT("phase_2A_static_home_courtyard_workshop_furniture_not_manipulable"));
    if(WorldName==TEXT("layout") || WorldName==TEXT("map")) D->SetStringField(TEXT("world_scope"),TEXT("configurable_static_scene_no_task_or_manipulation_semantics"));
    D->SetBoolField(TEXT("ready"),bAvatarLoaded && (!Profile.bProvided || (AnimatedBody && AnimatedBody->GetSkeletalMeshAsset() && (Profile.AnimationMode!=TEXT("clips") || (Locomotion.Num()==5 && !Locomotion.Contains(nullptr))))));
    D->SetStringField(TEXT("engine_version"),FEngineVersion::Current().ToString());
    D->SetStringField(TEXT("timing"),TEXT("command_stepped_kinematics_not_physics_lockstep"));
    D->SetStringField(TEXT("units"),TEXT("centimeters_degrees_seconds"));
    D->SetNumberField(TEXT("step_seconds"),StepSeconds);
    D->SetNumberField(TEXT("max_steps"),MaxSteps);
    D->SetStringField(TEXT("avatar"),AvatarPath);
    D->SetBoolField(TEXT("avatar_loaded"),bAvatarLoaded);
    D->SetNumberField(TEXT("avatar_yaw_offset_deg"),Avatar ? Avatar->GetRootComponent()->GetRelativeRotation().Yaw : 0);
    D->SetBoolField(TEXT("rgb_available"),bRGB);
    D->SetNumberField(TEXT("rgb_width"),160);
    D->SetNumberField(TEXT("rgb_height"),120);
    D->SetNumberField(TEXT("eye_exposure_bias"),Eye->PostProcessSettings.AutoExposureBias);
    D->SetNumberField(TEXT("observer_exposure_bias"),ObserverEye->PostProcessSettings.AutoExposureBias);
    D->SetStringField(TEXT("lighting"),WorldName==TEXT("room") ? TEXT("supplied_flat_reference_lighting") : TEXT("fixed_sun_sky_plus_unshadowed_ambient_fills_GI_disabled"));
    if(WorldName==TEXT("map")) D->SetStringField(TEXT("lighting"),TEXT("authored_map_lighting"));
    D->SetNumberField(TEXT("observer_width"),640);
    D->SetNumberField(TEXT("observer_height"),480);
    D->SetStringField(TEXT("action_space"),TEXT("forward,strafe,turn,look; finite numbers in [-1,1]"));
    D->SetStringField(TEXT("controller"),TEXT("supplied_kinematic_capsule_no_learned_locomotion"));
    D->SetNumberField(TEXT("speed_cm_s"),Profile.Speed);
    D->SetNumberField(TEXT("turn_deg_s"),Profile.TurnRate);
    D->SetNumberField(TEXT("look_deg_s"),Profile.LookRate);
    D->SetStringField(TEXT("animation_mode"),Profile.bProvided ? Profile.AnimationMode : TEXT("legacy"));
    D->SetStringField(TEXT("reward"),TEXT("zero_in_phase_1"));
    auto Map=MakeShared<FJsonObject>();
    Map->SetStringField(TEXT("layout"),WorldName);
    Map->SetArrayField(TEXT("bounds_cm"),WorldName==TEXT("room") ? TArray<TSharedPtr<FJsonValue>>{MakeShared<FJsonValueNumber>(-650),MakeShared<FJsonValueNumber>(-650),MakeShared<FJsonValueNumber>(1300),MakeShared<FJsonValueNumber>(1300)} : TArray<TSharedPtr<FJsonValue>>{MakeShared<FJsonValueNumber>(-1400),MakeShared<FJsonValueNumber>(-1250),MakeShared<FJsonValueNumber>(2800),MakeShared<FJsonValueNumber>(2500)});
    D->SetObjectField(TEXT("diagnostic_map"),Map);
    if(Profile.bProvided)
    {
        TArray<TSharedPtr<FJsonValue>> Values;for(double V:Profile.Bounds) Values.Add(MakeShared<FJsonValueNumber>(V));
        Map->SetArrayField(TEXT("bounds_cm"),Values);
    }
    return D;
}

TSharedRef<FJsonObject> AResearchEnvironment::Observe()
{
    auto D = MakeShared<FJsonObject>();
    D->SetStringField(TEXT("protocol"),TEXT("erl/1.0"));
    D->SetStringField(TEXT("episode_id"),Episode);
    D->SetNumberField(TEXT("step_index"),StepIndex);
    D->SetNumberField(TEXT("sim_time_s"),StepIndex * StepSeconds);
    D->SetNumberField(TEXT("reward"),0);
    D->SetBoolField(TEXT("terminated"),false);
    D->SetBoolField(TEXT("truncated"),StepIndex >= MaxSteps);
    auto O = MakeShared<FJsonObject>();
    auto P = MakeShared<FJsonObject>();
    P->SetNumberField(TEXT("heading_deg"),Heading);
    P->SetNumberField(TEXT("look_pitch_deg"),Pitch);
    P->SetArrayField(TEXT("local_velocity_cm_s"),Vec(GetActorRotation().UnrotateVector(LastVelocity)));
    O->SetObjectField(TEXT("proprioception"),P);
    auto C = MakeShared<FJsonObject>();
    C->SetBoolField(TEXT("blocked"),bBlocked);
    O->SetObjectField(TEXT("contacts"),C);
    if (bRGB && Image)
    {
        Eye->CaptureScene();
        TArray<FColor> Pixels;
        if (Image->GameThread_GetRenderTargetResource()->ReadPixels(Pixels))
        {
            TArray64<uint8> PNG;
            FImageUtils::PNGCompressImageArray(160,120,Pixels,PNG);
            auto R = MakeShared<FJsonObject>();
            R->SetStringField(TEXT("encoding"),TEXT("png_base64"));
            R->SetNumberField(TEXT("width"),160);
            R->SetNumberField(TEXT("height"),120);
            R->SetStringField(TEXT("data"),FBase64::Encode(PNG.GetData(),PNG.Num()));
            O->SetObjectField(TEXT("rgb"),R);
        }
        else O->SetField(TEXT("rgb"),MakeShared<FJsonValueNull>());
    }
    else O->SetField(TEXT("rgb"),MakeShared<FJsonValueNull>());
    D->SetObjectField(TEXT("observation"),O);
    auto Debug = MakeShared<FJsonObject>();
    Debug->SetArrayField(TEXT("position_cm"),Vec(GetActorLocation()));
    if(Obstacle) Debug->SetArrayField(TEXT("obstacle_position_cm"),Vec(Obstacle->GetActorLocation()));
    else Debug->SetField(TEXT("obstacle_position_cm"),MakeShared<FJsonValueNull>());
    Debug->SetNumberField(TEXT("seed"),Seed);
    Debug->SetStringField(TEXT("last_hit_actor"),LastHitActor);
    Debug->SetStringField(TEXT("animation_state"),AnimationState);
    Debug->SetNumberField(TEXT("gait_phase_s"),GaitPhase);
    if (bRGB && ObserverImage)
    {
        ObserverEye->CaptureScene();
        TArray<FColor> Pixels;
        if (ObserverImage->GameThread_GetRenderTargetResource()->ReadPixels(Pixels))
        {
            TArray64<uint8> PNG;
            FImageUtils::PNGCompressImageArray(640,480,Pixels,PNG);
            auto R = MakeShared<FJsonObject>();
            R->SetStringField(TEXT("encoding"),TEXT("png_base64"));
            R->SetNumberField(TEXT("width"),640);
            R->SetNumberField(TEXT("height"),480);
            R->SetStringField(TEXT("data"),FBase64::Encode(PNG.GetData(),PNG.Num()));
            Debug->SetObjectField(TEXT("observer_rgb"),R);
        }
    }
    D->SetObjectField(TEXT("privileged"),Debug);
    return D;
}

bool AResearchEnvironment::Handle(const FHttpServerRequest& Request, const FHttpResultCallback& Complete, const FString& Op)
{
    const auto* Header = Request.Headers.Find(TEXT("x-erl-token"));
    if (!Header || Header->Num()!=1 || (*Header)[0]!=Token) { Fail(Complete,401,TEXT("unauthorized")); return true; }
    if (Op==TEXT("health") || Op==TEXT("spec")) { Reply(Complete,Describe()); return true; }
    if(bCapturePending) {Fail(Complete,503,TEXT("pose_capture_pending"));return true;}
    if(Op==TEXT("layout"))
    {
        if(WorldName!=TEXT("home") && WorldName!=TEXT("layout")) {Fail(Complete,400,TEXT("only_home_or_layout_geometry_can_be_exported"));return true;}
        auto D=MakeShared<FJsonObject>();D->SetStringField(TEXT("protocol"),TEXT("erl/1.0"));
        D->SetStringField(TEXT("scope"),TEXT("privileged_static_geometry_snapshot_not_dynamic_world_reset"));
        TArray<TSharedPtr<FJsonValue>> Values;
        bool Valid=true;
        auto Add=[&Values,&Valid](UStaticMeshComponent* Mesh,const FTransform& Transform)
        {
            if(!Mesh->GetStaticMesh() || !Mesh->GetMaterial(0)) {Valid=false;return;}
            auto O=MakeShared<FJsonObject>();
            O->SetArrayField(TEXT("position_cm"),Vec(Transform.GetLocation()));
            O->SetArrayField(TEXT("size_cm"),Vec(Transform.GetScale3D()*100));
            const auto R=Transform.Rotator();O->SetArrayField(TEXT("rotation_deg"),Vec(FVector(R.Pitch,R.Yaw,R.Roll)));
            O->SetStringField(TEXT("shape"),Mesh->GetStaticMesh()->GetName());
            O->SetStringField(TEXT("material"),Mesh->GetMaterial(0)->GetPathName());
            O->SetBoolField(TEXT("collision"),Mesh->GetCollisionEnabled()!=ECollisionEnabled::NoCollision);
            Values.Add(MakeShared<FJsonValueObject>(O));
        };
        TArray<FString> Keys;Pieces.GetKeys(Keys);Keys.Sort();
        for(const auto& Key:Keys)
        {
            auto* Mesh=Pieces[Key].Get();
            for(int32 I=0;I<Mesh->GetInstanceCount();++I) {FTransform Transform;Mesh->GetInstanceTransform(I,Transform,true);Add(Mesh,Transform);}
        }
        if(Obstacle)
            if(auto* Mesh=Cast<UStaticMeshComponent>(Obstacle->GetComponentByClass(UStaticMeshComponent::StaticClass()))) Add(Mesh,Mesh->GetComponentTransform());
        if(!Valid) {Fail(Complete,503,TEXT("geometry_material_not_ready"));return true;}
        D->SetArrayField(TEXT("pieces"),Values);Reply(Complete,D);return true;
    }
    if (Op==TEXT("overview"))
    {
        if(!bRGB || !ObserverImage) {Fail(Complete,503,TEXT("renderer_unavailable"));return true;}
        const FTransform Before=ObserverEye->GetComponentTransform();
        const FVector Location=Profile.Overview;
        const FVector Center(Profile.Bounds[0]+Profile.Bounds[2]/2,-(Profile.Bounds[1]+Profile.Bounds[3]/2),0);
        ObserverEye->SetWorldLocationAndRotation(Location,(Center-Location).Rotation());
        ObserverEye->CaptureScene();
        TArray<FColor> Pixels;
        const bool Captured=ObserverImage->GameThread_GetRenderTargetResource()->ReadPixels(Pixels);
        ObserverEye->SetWorldTransform(Before);
        if(!Captured) {Fail(Complete,503,TEXT("capture_failed"));return true;}
        TArray64<uint8> PNG;
        FImageUtils::PNGCompressImageArray(640,480,Pixels,PNG);
        auto D=MakeShared<FJsonObject>();
        D->SetStringField(TEXT("protocol"),TEXT("erl/1.0"));
        auto RGB=MakeShared<FJsonObject>();
        RGB->SetStringField(TEXT("encoding"),TEXT("png_base64"));
        RGB->SetNumberField(TEXT("width"),640);RGB->SetNumberField(TEXT("height"),480);
        RGB->SetStringField(TEXT("data"),FBase64::Encode(PNG.GetData(),PNG.Num()));
        D->SetObjectField(TEXT("rgb"),RGB);
        D->SetStringField(TEXT("scope"),TEXT("privileged_research_camera_not_policy_observation"));
        Reply(Complete,D);return true;
    }
    if (Op==TEXT("observe")) { Reply(Complete,Observe()); return true; }
    if(!bAvatarLoaded || (Profile.bProvided && (!AnimatedBody || !AnimatedBody->GetSkeletalMeshAsset() || (Profile.AnimationMode==TEXT("clips") && (Locomotion.Num()!=5 || Locomotion.Contains(nullptr))))))
    {Fail(Complete,503,TEXT("avatar_or_animation_not_ready"));return true;}
    if (Request.Body.Num()>4096) { Fail(Complete,413,TEXT("body_too_large")); return true; }
    FUTF8ToTCHAR Text(reinterpret_cast<const ANSICHAR*>(Request.Body.GetData()),Request.Body.Num());
    TSharedPtr<FJsonObject> Data;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(FString(Text.Length(),Text.Get())),Data) || !Data)
    { Fail(Complete,400,TEXT("invalid_json")); return true; }
    if (Op==TEXT("reset"))
    {
        double Value;
        if (Data->Values.Num()!=1 || !Data->HasTypedField<EJson::Number>(TEXT("seed")) || !Data->TryGetNumberField(TEXT("seed"),Value) || !FMath::IsFinite(Value) || Value<0 || Value>2147483647 || Value!=FMath::FloorToDouble(Value))
        { Fail(Complete,400,TEXT("seed_must_be_int32_nonnegative")); return true; }
        ResetState(static_cast<int32>(Value));
        ReplyAfterPose(Complete);
        return true;
    }
    FString ExpectedEpisode;
    double ExpectedStep;
    const TSharedPtr<FJsonObject>* Action = nullptr;
    if (Data->Values.Num()!=3 || !Data->HasTypedField<EJson::Number>(TEXT("expected_step")) || !Data->TryGetStringField(TEXT("episode_id"),ExpectedEpisode) || !Data->TryGetNumberField(TEXT("expected_step"),ExpectedStep) ||
        !Data->TryGetObjectField(TEXT("action"),Action) || !Action || (*Action)->Values.Num()!=4)
    { Fail(Complete,400,TEXT("invalid_step_envelope")); return true; }
    double Values[4];
    const TCHAR* Keys[] = {TEXT("forward"),TEXT("strafe"),TEXT("turn"),TEXT("look")};
    for (int I=0; I<4; ++I)
        if (!(*Action)->HasTypedField<EJson::Number>(Keys[I]) || !(*Action)->TryGetNumberField(Keys[I],Values[I]) || !FMath::IsFinite(Values[I]) || FMath::Abs(Values[I])>1)
        { Fail(Complete,400,TEXT("invalid_action")); return true; }
    if (ExpectedEpisode!=Episode || ExpectedStep!=StepIndex || StepIndex>=MaxSteps)
    { Fail(Complete,409,TEXT("episode_or_step_conflict")); return true; }
    if(!bAvatarLoaded || (Profile.bProvided && Profile.AnimationMode==TEXT("clips") && AnimationState!=TEXT("idle") && !AnimationState.StartsWith(TEXT("walk_"))))
    {Fail(Complete,503,TEXT("avatar_or_animation_not_ready"));return true;}
    Heading = FRotator::NormalizeAxis(Heading + Values[2]*Profile.TurnRate*StepSeconds);
    Pitch = FMath::Clamp(Pitch + Values[3]*Profile.LookRate*StepSeconds,-70.0,70.0);
    SetActorRotation(FRotator(0,Heading,0));
    Eye->SetRelativeRotation(FRotator(Pitch,0,0));
    FVector Local(Values[0],Values[1],0);
    Local = Local.GetClampedToMaxSize(1);
    const FVector Delta = GetActorRotation().RotateVector(Local)*Profile.Speed*StepSeconds;
    const FVector Before = GetActorLocation();
    FHitResult Hit;
    AddActorWorldOffset(Delta,true,&Hit);
    bBlocked = Hit.bBlockingHit;
    LastHitActor = Hit.GetActor() ? Hit.GetActor()->GetName() : TEXT("");
    LastVelocity = (GetActorLocation()-Before)/StepSeconds;
    ++StepIndex;
    UpdateAnimation();
    ReplyAfterPose(Complete);
    return true;
}

void AResearchEnvironment::ReplyAfterPose(const FHttpResultCallback& Complete)
{
    // Let attached face/groom components consume the new skeletal pose before capture.
    // Serialize mutations while the one outstanding response is being assembled.
    bCapturePending=true;
    GetWorld()->GetTimerManager().SetTimerForNextTick([Weak=TWeakObjectPtr<AResearchEnvironment>(this),Complete]()
    {
        if(!Weak.IsValid()) {Fail(Complete,503,TEXT("environment_unavailable"));return;}
        Weak->bCapturePending=false;
        Reply(Complete,Weak->Observe());
    });
}

void AResearchEnvironment::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Router) for (const auto& Route : Routes) if (Route) Router->UnbindRoute(Route);
    if(WorldGeometry) WorldGeometry->Destroy();
    Routes.Empty();
    Router.Reset();
    Super::EndPlay(Reason);
}

bool UResearchWorldSubsystem::DoesSupportWorldType(EWorldType::Type Type) const
{
    return Type == EWorldType::Game || Type == EWorldType::PIE;
}
void UResearchWorldSubsystem::OnWorldBeginPlay(UWorld& World)
{
    Super::OnWorldBeginPlay(World);
    if (FParse::Param(FCommandLine::Get(),TEXT("ERL")))
    {
        FResearchProfile P;FString Error;
        if(!FResearchProfile::Load(P,Error)) {UE_LOG(LogTemp,Error,TEXT("ERL: %s"),*Error);return;}
        if(P.bProvided)
        {
            for(const auto& M:P.Document->GetArrayField(TEXT("mounts")))
            {
                auto O=M->AsObject();FString Root=FPaths::ConvertRelativePathToFull(O->GetStringField(TEXT("directory")));
                FPaths::NormalizeDirectoryName(Root);
                FPackageName::RegisterMountPoint(O->GetStringField(TEXT("virtual")),Root+TEXT("/"));
            }
            if(P.Kind==TEXT("map") && World.GetOutermost()->GetName()!=P.Map)
            {
                if(!FPackageName::DoesPackageExist(P.Map)) {UE_LOG(LogTemp,Error,TEXT("ERL: custom map missing: %s"),*P.Map);return;}
                UGameplayStatics::OpenLevel(&World,FName(*P.Map));return;
            }
        }
        // Mount after engine initialization/self-tests, before loading the avatar.
        FString Root;
        if (!P.bProvided && FParse::Value(FCommandLine::Get(),TEXT("ERLContentRoot="),Root))
        {
            Root = FPaths::ConvertRelativePathToFull(Root);
            FPaths::NormalizeDirectoryName(Root);
            FPackageName::RegisterMountPoint(TEXT("/Game/"),Root + TEXT("/"));
        }
        World.SpawnActor<AResearchEnvironment>();
    }
}
