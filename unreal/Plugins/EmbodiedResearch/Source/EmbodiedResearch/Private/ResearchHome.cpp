#include "ResearchEnvironment.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/TextureCube.h"
#include "Engine/DirectionalLight.h"
#include "Engine/PointLight.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"

// World units are cm. Static instances share mesh/material draw calls.
// Furniture is scenery in this increment, not a claim of general manipulation.
void AResearchEnvironment::Piece(const FVector& P,const FVector& Size,const FString& Mat,const FString& Shape,const FRotator& Rot,bool Collision)
{
    const FString Key=Shape+Mat+(Collision ? TEXT("solid") : TEXT("decor"));
    auto* Mesh=Pieces.FindRef(Key).Get();
    if (!Mesh)
    {
        Mesh=NewObject<UInstancedStaticMeshComponent>(WorldGeometry);
        Mesh->SetMobility(EComponentMobility::Movable);
        Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,Mat==TEXT("Sky") ? TEXT("/Engine/EngineSky/SM_SkySphere.SM_SkySphere") : *(TEXT("/Engine/BasicShapes/")+Shape+TEXT(".")+Shape)));
        auto* Material=LoadObject<UMaterialInterface>(nullptr,*(Mat.StartsWith(TEXT("/")) ? Mat : TEXT("/EmbodiedResearch/Materials/M_")+Mat));
        if (Material) Mesh->SetMaterial(0,Material);
        else UE_LOG(LogTemp,Error,TEXT("ERL home material missing: %s"),*Mat);
        Mesh->SetCollisionProfileName(Collision ? TEXT("BlockAll") : TEXT("NoCollision"));
        if(Mat==TEXT("Sky")) Mesh->SetCastShadow(false);
        Mesh->SetupAttachment(WorldGeometry->GetRootComponent());
        WorldGeometry->AddInstanceComponent(Mesh);
        Mesh->RegisterComponent();
        Pieces.Add(Key,Mesh);
    }
    Mesh->AddInstance(FTransform(Rot,P,Size/100.0),true);
}

void AResearchEnvironment::CreateHome()
{
    WorldGeometry=GetWorld()->SpawnActor<AActor>();
    auto* Root=NewObject<USceneComponent>(WorldGeometry);
    WorldGeometry->SetRootComponent(Root);
    WorldGeometry->AddInstanceComponent(Root);
    Root->RegisterComponent();
    // An enclosed 26 x 23 m plot. Home west, workshop east, open courtyard north.
    Piece({0,0,-18},{2800,2500,36},TEXT("Soil"));
    for(int X=-1250;X<=1250;X+=100) for(int Y=-1050;Y<=1050;Y+=100)
        Piece({double(X),double(Y),-5},{98,98,10},((X+Y)/100)%3==0 ? TEXT("Plaster") : TEXT("Stone"));
    for(int X=-1050;X<50;X+=100) for(int Y=-775;Y<0;Y+=25)
        Piece({double(X+(Y/25%2)*25),double(Y),-2},{99,24,4},TEXT("Oak"));
    for(int X=-1300;X<=1300;X+=260)
        Piece({double(X),1150,100},{258,20,200},TEXT("Plaster"));
    Piece({-1300,0,100},{20,2300,200},TEXT("Plaster"));
    Piece({1300,0,100},{20,2300,200},TEXT("Plaster"));
    Piece({0,-1150,100},{2600,20,200},TEXT("Plaster"));
    // Home shell. Open portals and recessed window openings are traversable only at doors.
    Piece({-1100,-400,150},{20,820,300},TEXT("Plaster"));
    Piece({100,-400,150},{20,820,300},TEXT("Plaster"));
    Piece({-500,-810,150},{1220,20,300},TEXT("Plaster"));
    Piece({-870,0,150},{460,20,300},TEXT("Plaster"));
    Piece({-490,0,45},{300,20,90},TEXT("Plaster"));
    Piece({-490,0,275},{300,20,50},TEXT("Plaster"));
    Piece({-330,0,150},{20,20,300},TEXT("Plaster"));
    Piece({-40,0,150},{280,20,300},TEXT("Plaster"));
    Piece({-250,0,275},{140,20,50},TEXT("Plaster")); // 140 cm open door
    for(double X : {-630.,-350.}) Piece({X,-3,170},{7,27,170},TEXT("Walnut"));
    Piece({-490,0,90},{300,32,8},TEXT("Walnut"));
    Piece({-490,0,251},{300,28,6},TEXT("Walnut"));
    Piece({-490,0,170},{5,23,160},TEXT("Walnut"));
    Piece({-500,-400,307},{1260,880,14},TEXT("Plaster"));
    for(double X : {-1085.,85.}) Piece({X,-400,12},{5,800,24},TEXT("Walnut"));
    Piece({-500,-794,12},{1180,5,24},TEXT("Walnut"));
    // Sofa, loose cushions and a woven rug in the living area.
    Piece({-870,-530,26},{112,270,30},TEXT("Walnut"));
    Piece({-900,-530,70},{38,270,92},TEXT("Linen"));
    Piece({-850,-661,62},{105,18,76},TEXT("Linen"));
    Piece({-850,-399,62},{105,18,76},TEXT("Linen"));
    for(double Y : {-610.,-530.,-450.})
    {
        Piece({-840,Y,48},{85,77,24},TEXT("Cream"));
        Piece({-880,Y,86},{18,68,60},TEXT("Cream"),TEXT("Cube"),FRotator(0,0,-10));
    }
    Piece({-635,-525,1},{240,330,2},TEXT("Linen"),TEXT("Cube"),FRotator::ZeroRotator,false);
    Piece({-620,-525,43},{100,170,8},TEXT("Walnut"));
    for(double X : {-658.,-582.}) for(double Y : {-590.,-460.}) Piece({X,Y,21},{5,5,42},TEXT("Metal"));
    Piece({-620,-540,50},{28,38,6},TEXT("Blue"),TEXT("Cube"),FRotator(0,8,0),false);
    Piece({-620,-540,54},{25,35,2},TEXT("Paper"),TEXT("Cube"),FRotator(0,8,0),false);
    // Kitchen counter and sink, with cabinet seams, handles and shelves.
    Piece({-260,-745,43},{570,100,86},TEXT("Walnut"));
    Piece({-260,-745,90},{585,108,8},TEXT("Stone"));
    for(int X=-510;X<=-10;X+=100)
    {
        Piece({double(X),-692,42},{96,3,78},TEXT("Oak"));
        Piece({double(X),-688,70},{22,3,2},TEXT("Metal"));
    }
    Piece({-200,-744,95},{100,60,3},TEXT("Steel"));
    Piece({-200,-744,97},{78,40,3},TEXT("Metal"));
    Piece({-200,-773,113},{4,4,35},TEXT("Steel"),TEXT("Cylinder"));
    Piece({-200,-762,129},{4,25,4},TEXT("Steel"));
    for(double Z : {160.,215.}) Piece({-260,-778,Z},{450,45,5},TEXT("Oak"));
    for(int I=0;I<5;++I) Piece({-390.+I*55,-776,174},{22,22,24},I%2 ? TEXT("Terracotta") : TEXT("Cream"),TEXT("Cylinder"),FRotator::ZeroRotator,false);
    // Dining table with four chairs.
    Piece({-200,-330,76},{150,100,6},TEXT("Oak"));
    for(double X : {-260.,-140.}) for(double Y : {-365.,-295.}) Piece({X,Y,36},{6,6,72},TEXT("Walnut"));
    for(double X : {-245.,-155.}) for(double Y : {-425.,-235.})
    {
        Piece({X,Y,45},{42,42,5},TEXT("Oak"));
        for(double DX : {-16.,16.}) for(double DY : {-16.,16.}) Piece({X+DX,Y+DY,22},{4,4,44},TEXT("Walnut"));
        Piece({X,Y+(Y<-300 ? -19:19),69},{42,4,48},TEXT("Oak"));
    }
    // Workshop: open doorway, workbench, tool board, shelves, storage and stool.
    Piece({350,-400,150},{20,820,300},TEXT("Plaster"));
    Piece({1100,-400,150},{20,820,300},TEXT("Plaster"));
    Piece({725,-810,150},{770,20,300},TEXT("Plaster"));
    Piece({460,0,150},{240,20,300},TEXT("Plaster"));
    Piece({920,0,150},{380,20,300},TEXT("Plaster"));
    Piece({650,0,275},{140,20,50},TEXT("Plaster"));
    Piece({725,-400,307},{810,880,14},TEXT("Walnut"));
    Piece({730,-730,92},{550,120,10},TEXT("Oak"));
    for(double X : {490.,970.}) for(double Y : {-775.,-685.}) Piece({X,Y,44},{8,8,88},TEXT("Metal"));
    Piece({730,-788,178},{480,6,120},TEXT("Walnut"));
    for(int I=0;I<9;++I)
    {
        Piece({540.+I*42,-779,179},{4,4,38},TEXT("Steel"),TEXT("Cylinder"),FRotator(0,0,I%2 ? 15:-15),false);
        Piece({540.+I*42,-779,157},{7,7,18},I%2 ? TEXT("Terracotta"):TEXT("Blue"),TEXT("Cylinder"),FRotator::ZeroRotator,false);
    }
    Piece({730,-640,49},{42,42,8},TEXT("Oak"),TEXT("Cylinder"));
    for(double X : {715.,745.}) for(double Y : {-655.,-625.}) Piece({X,Y,23},{4,4,46},TEXT("Metal"));
    for(double Z : {35.,100.,165.,230.}) Piece({1045,-360,Z},{70,380,6},TEXT("Oak"));
    for(double Y : {-530.,-190.}) for(double X : {1015.,1075.}) Piece({X,Y,134},{5,5,268},TEXT("Metal"));
    for(int I=0;I<6;++I) Piece({1045,-490.+(I%3)*120,58.+(I/3)*65},{55,80,40},I%2?TEXT("Blue"):TEXT("Terracotta"));
    // Courtyard planters, a central olive-like tree, benches and pergola.
    auto Plant=[this](FVector P,double S)
    {
        Piece(P+FVector(0,0,22*S),FVector(65,65,44)*S,TEXT("Terracotta"),TEXT("Cylinder"));
        Piece(P+FVector(0,0,45*S),FVector(58,58,4)*S,TEXT("Soil"),TEXT("Cylinder"));
        Piece(P+FVector(0,0,100*S),FVector(9,9,120)*S,TEXT("Walnut"),TEXT("Cylinder"));
        for(int I=0;I<7;++I)
        {
            const double A=I*2.399;
            Piece(P+FVector(FMath::Cos(A)*30*S,FMath::Sin(A)*30*S,(145+(I%3)*15)*S),FVector(70,60,70)*S,TEXT("Leaves"),TEXT("Sphere"),FRotator::ZeroRotator,false);
        }
    };
    Plant({-1050,350,0},1); Plant({-1050,950,0},1.3); Plant({1050,950,0},1.2); Plant({1150,-100,0},.75);
    Plant({100,670,0},1.7);
    for(double X : {-450.,650.})
    {
        for(int I=0;I<5;++I) Piece({X,950.+I*10,46},{210,8,7},TEXT("Oak"));
        Piece({X,1000,76},{210,8,55},TEXT("Oak"));
        for(double DX : {-80.,80.}) Piece({X+DX,965,22},{9,45,44},TEXT("Metal"));
    }
    for(double X : {-850.,-50.}) for(double Y : {160.,780.}) Piece({X,Y,142},{16,16,284},TEXT("Walnut"));
    for(int I=0;I<12;++I) Piece({-850.+I*73,470,294},{12,740,14},TEXT("Walnut"));
    Piece({-460,440,74},{220,100,7},TEXT("Oak"));
    for(double X : {-545.,-375.}) for(double Y : {405.,475.}) Piece({X,Y,36},{7,7,72},TEXT("Metal"));
    // Seeded diagnostic crate remains outside the initial route.
    Obstacle=AddBlock({220,150,35},{70,70,70},TEXT("seeded_crate"));
    if (auto* C=Cast<UStaticMeshComponent>(Obstacle->GetComponentByClass(UStaticMeshComponent::StaticClass())))
        C->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/EmbodiedResearch/Materials/M_Oak")));
    CreateDaylight();
    UE_LOG(LogTemp,Display,TEXT("ERL_HOME_READY batches=%d"),Pieces.Num());
}

void AResearchEnvironment::CreateLayout()
{
    WorldGeometry=GetWorld()->SpawnActor<AActor>();
    auto* Root=NewObject<USceneComponent>(WorldGeometry);
    WorldGeometry->SetRootComponent(Root);WorldGeometry->AddInstanceComponent(Root);Root->RegisterComponent();
    for(const auto& V:Profile.Document->GetObjectField(TEXT("world"))->GetArrayField(TEXT("pieces")))
    {
        auto O=V->AsObject();
        auto Vector=[&O](const TCHAR* Key){const auto& A=O->GetArrayField(Key);return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());};
        const FVector R=Vector(TEXT("rotation_deg"));
        Piece(Vector(TEXT("position_cm")),Vector(TEXT("size_cm")),O->GetStringField(TEXT("material")),O->GetStringField(TEXT("shape")),FRotator(R.X,R.Y,R.Z),O->GetBoolField(TEXT("collision")));
    }
    CreateDaylight();
    UE_LOG(LogTemp,Display,TEXT("ERL_LAYOUT_READY batches=%d"),Pieces.Num());
}

void AResearchEnvironment::CreateDaylight()
{
    auto* Atmosphere=NewObject<USkyAtmosphereComponent>(WorldGeometry);
    WorldGeometry->AddInstanceComponent(Atmosphere);
    Atmosphere->SetupAttachment(WorldGeometry->GetRootComponent());
    Atmosphere->RegisterComponent();
    auto* Sun=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-48,-35,0));
    Sun->GetComponent()->SetIntensity(3.0f);
    Sun->GetComponent()->SetLightColor(FLinearColor(1,.92f,.79f));
    Sun->GetComponent()->SetCastShadows(true);
    Sun->GetComponent()->SetAtmosphereSunLight(true);
    // Supplied ambient approximation replaces costly diffuse GI on this machine.
    // These fills are recorded as renderer assistance, not physically accurate light transport.
    for(int32 I=0;I<4;++I)
    {
        auto* Fill=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-40,45+90*I,0));
        Fill->GetComponent()->SetIntensity(.65f);
        Fill->GetComponent()->SetLightColor(FLinearColor(.82f,.90f,1.f));
        Fill->GetComponent()->SetCastShadows(false);
    }
    auto* Sky=GetWorld()->SpawnActor<ASkyLight>();
    Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    Sky->GetLightComponent()->SourceType=SLS_SpecifiedCubemap;
    Sky->GetLightComponent()->SetCubemap(LoadObject<UTextureCube>(nullptr,TEXT("/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap")));
    Sky->GetLightComponent()->SetIntensity(2.0f);
    Sky->GetLightComponent()->SetCastShadows(false);
    Sky->GetLightComponent()->RecaptureSky();
    for(FVector P : {FVector(-500,-400,260),FVector(725,-400,260)})
    {
        auto* Light=GetWorld()->SpawnActor<APointLight>(P,FRotator::ZeroRotator);
        Light->PointLightComponent->SetIntensity(9000);
        Light->PointLightComponent->SetLightColor(FLinearColor(1,.88f,.70f));
        Light->PointLightComponent->SetAttenuationRadius(1000);
        Light->PointLightComponent->SetCastShadows(false);
    }
    UE_LOG(LogTemp,Display,TEXT("ERL_DAYLIGHT_READY"));
}

void AResearchEnvironment::SetupAnimation()
{
    if (!Avatar || (!Profile.bProvided && WorldName==TEXT("room"))) return;
    // Optional MetaHuman groom components expose this reflected API. Avoid making
    // the reusable body adapter depend on the optional HairStrands plugin module.
    TArray<UActorComponent*> AvatarComponents;
    Avatar->GetComponents(AvatarComponents);
    for(auto* Component : AvatarComponents)
        if(Profile.bDisableGroom && Component->GetClass()->GetName()==TEXT("GroomComponent"))
            if(auto* DisableSimulation=Component->FindFunction(TEXT("SetEnableSimulation")))
            {
                bool Enabled=false;
                Component->ProcessEvent(DisableSimulation,&Enabled);
            }
    TArray<USkeletalMeshComponent*> Meshes;
    Avatar->GetComponents(Meshes);
    for(auto* Mesh : Meshes) if(Mesh->GetName().Equals(Profile.BodyComponent,ESearchCase::IgnoreCase)) AnimatedBody=Mesh;
    if(!AnimatedBody || !AnimatedBody->GetSkeletalMeshAsset()) {AnimationState=TEXT("missing_body_or_mesh");UE_LOG(LogTemp,Error,TEXT("ERL: skeletal component or mesh missing: %s"),*Profile.BodyComponent);return;}
    if(Profile.bProvided && Profile.AnimationMode!=TEXT("clips"))
    {
        AnimationState=Profile.AnimationMode==TEXT("existing") ? TEXT("existing_animation_blueprint") : TEXT("reference_pose");
        if(Profile.AnimationMode==TEXT("none")) {AnimatedBody->SetAnimationMode(EAnimationMode::AnimationSingleNode);AnimatedBody->SetAnimation(nullptr);}
        return;
    }
    const TCHAR* Names[]={TEXT("MM_Idle"),TEXT("MF_Unarmed_Walk_Fwd"),TEXT("MF_Unarmed_Walk_Bwd"),TEXT("MF_Unarmed_Walk_Left"),TEXT("MF_Unarmed_Walk_Right")};
    if(Profile.bProvided) for(const auto& Path:Profile.Clips) Locomotion.Add(LoadObject<UAnimSequence>(nullptr,*Path));
    else for(auto* Name : Names) Locomotion.Add(LoadObject<UAnimSequence>(nullptr,*(FString(TEXT("/EmbodiedResearch/Animation/Bob_"))+Name)));
    if(!AnimatedBody || Locomotion.Contains(nullptr)) {AnimationState=TEXT("missing_assets");return;}
    for(const auto& Clip:Locomotion)
        if(Clip->GetSkeleton()!=AnimatedBody->GetSkeletalMeshAsset()->GetSkeleton())
        {AnimationState=TEXT("skeleton_mismatch");UE_LOG(LogTemp,Error,TEXT("ERL: retarget %s to the selected avatar skeleton first"),*Clip->GetPathName());Locomotion.Empty();return;}
    AnimatedBody->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    AnimatedBody->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    // API step drives pose time. Render ticks never advance the supplied sequence.
    AnimatedBody->SetComponentTickEnabled(false);
    UpdateAnimation();
}

void AResearchEnvironment::UpdateAnimation()
{
    if(!AnimatedBody || Locomotion.Num()!=5 || Locomotion.Contains(nullptr)) return;
    const FVector V=GetActorRotation().UnrotateVector(LastVelocity);
    int32 Index=0;
    if(V.Size2D()>5)
    {
        if(FMath::Abs(V.X)>=FMath::Abs(V.Y)) Index=V.X>0 ? 1:2;
        else Index=V.Y<0 ? 3:4;
        GaitPhase=FMath::Fmod(GaitPhase+float(StepSeconds)*V.Size2D()/Profile.Speed,Locomotion[Index]->GetPlayLength());
    }
    else GaitPhase=FMath::Fmod(float(StepIndex)*float(StepSeconds),Locomotion[0]->GetPlayLength());
    const TCHAR* States[]={TEXT("idle"),TEXT("walk_forward"),TEXT("walk_backward"),TEXT("walk_left"),TEXT("walk_right")};
    AnimationState=States[Index];
    auto* Anim=AnimatedBody->GetSingleNodeInstance();
    if(!Anim) return;
    if(Anim->GetAnimationAsset()!=Locomotion[Index]) Anim->SetAnimationAsset(Locomotion[Index],true,0.f);
    Anim->SetPosition(FMath::Fmod(GaitPhase,Locomotion[Index]->GetPlayLength()),false);
    Anim->SetPlaying(false);
    AnimatedBody->TickAnimation(0,false);
    AnimatedBody->RefreshBoneTransforms();
    for(const auto& Child : AnimatedBody->GetAttachChildren()) if(auto* Skel=Cast<USkeletalMeshComponent>(Child.Get()))
    {
        Skel->TickAnimation(0,false);
        Skel->RefreshBoneTransforms();
    }
}
