#include "ResearchProfile.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"

namespace
{
bool Text(const TSharedPtr<FJsonObject>& O,const TCHAR* Key,FString& Value)
{
    return O && O->TryGetStringField(Key,Value) && !Value.IsEmpty();
}
bool Num(const TSharedPtr<FJsonObject>& O,const TCHAR* Key,double& Value,double Low,double High)
{
    return O && O->HasTypedField<EJson::Number>(Key) && O->TryGetNumberField(Key,Value) && FMath::IsFinite(Value) && Value>=Low && Value<=High;
}
bool Vector(const TSharedPtr<FJsonObject>& O,const TCHAR* Key,FVector& Value,double Low=-1e7,double High=1e7)
{
    const TArray<TSharedPtr<FJsonValue>>* A;
    if(!O || !O->TryGetArrayField(Key,A) || A->Num()!=3) return false;
    double V[3];
    for(int I=0;I<3;++I) if((*A)[I]->Type!=EJson::Number || !(*A)[I]->TryGetNumber(V[I]) || !FMath::IsFinite(V[I]) || V[I]<Low || V[I]>High) return false;
    Value=FVector(V[0],V[1],V[2]);return true;
}
}

bool FResearchProfile::Load(FResearchProfile& P,FString& Error)
{
    if(!FParse::Value(FCommandLine::Get(),TEXT("ERLConfig="),P.SnapshotPath)) return true;
    P.bProvided=true;
    FString Json;
    Error=TEXT("Invalid ERL profile: use erl.manage validate/doctor and a resolved profile snapshot");
    if(!FFileHelper::LoadFileToString(Json,*P.SnapshotPath) || Json.Len()>8*1024*1024 ||
       !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),P.Document) || !P.Document) return false;
    FString Format;
    if(!Text(P.Document,TEXT("format"),Format) || Format!=TEXT("erl-experiment/1.0") || !Text(P.Document,TEXT("id"),P.Id)) return false;
    const TSharedPtr<FJsonObject> *W,*A,*C,*R;
    if(!P.Document->TryGetObjectField(TEXT("world"),W) || !P.Document->TryGetObjectField(TEXT("avatar"),A) ||
       !P.Document->TryGetObjectField(TEXT("control"),C) || !P.Document->TryGetObjectField(TEXT("render"),R)) return false;
    if(!Text(*W,TEXT("kind"),P.Kind) || !TArray<FString>{TEXT("home"),TEXT("room"),TEXT("layout"),TEXT("map")}.Contains(P.Kind) ||
       !Text(*W,TEXT("map"),P.Map) || !P.Map.StartsWith(TEXT("/")) || P.Map.Contains(TEXT("..")) ||
       !Vector(*W,TEXT("spawn_cm"),P.Spawn) || !Vector(*W,TEXT("overview_cm"),P.Overview)) return false;
    const TArray<TSharedPtr<FJsonValue>>* Bounds;
    if(!(*W)->TryGetArrayField(TEXT("bounds_cm"),Bounds) || Bounds->Num()!=4) return false;
    P.Bounds.Empty();
    for(const auto& V:*Bounds)
    {
        double N;if(V->Type!=EJson::Number || !V->TryGetNumber(N) || !FMath::IsFinite(N)) return false;
        P.Bounds.Add(N);
    }
    if(P.Bounds[2]<=0 || P.Bounds[3]<=0) return false;
    double N;
    if(!Num(*W,TEXT("heading_deg"),N,-180,180)) return false;P.Heading=N;
    if(!Text(*A,TEXT("kind"),P.AvatarKind) || !TArray<FString>{TEXT("blueprint"),TEXT("skeletal_mesh")}.Contains(P.AvatarKind) ||
       !Text(*A,TEXT("asset"),P.AvatarAsset) || !P.AvatarAsset.StartsWith(TEXT("/")) ||
       !Text(*A,TEXT("body_component"),P.BodyComponent) || !Vector(*A,TEXT("offset_cm"),P.Offset) ||
       !Vector(*A,TEXT("scale"),P.Scale,.001,1000) || !Vector(*A,TEXT("eye_offset_cm"),P.EyeOffset)) return false;
    if(!Num(*A,TEXT("capsule_radius_cm"),N,1,1000)) return false;P.Radius=N;
    if(!Num(*A,TEXT("capsule_half_height_cm"),N,P.Radius,2000)) return false;P.HalfHeight=N;
    if(!Num(*A,TEXT("yaw_deg"),N,-180,180)) return false;P.Yaw=N;
    if(!Num(*C,TEXT("max_steps"),N,1,10000000) || FMath::FloorToDouble(N)!=N) return false;P.MaxSteps=N;
    if(!Num(*C,TEXT("speed_cm_s"),N,.01,10000)) return false;P.Speed=N;
    if(!Num(*C,TEXT("turn_deg_s"),N,.01,10000)) return false;P.TurnRate=N;
    if(!Num(*C,TEXT("look_deg_s"),N,.01,10000)) return false;P.LookRate=N;
    if(!Num(*R,TEXT("eye_exposure"),N,-8,8)) return false;P.EyeExposure=N;
    if(!Num(*R,TEXT("observer_exposure"),N,-8,8)) return false;P.ObserverExposure=N;
    const TSharedPtr<FJsonObject> *Anim,*Clips;
    if(!(*A)->TryGetObjectField(TEXT("animation"),Anim) || !Text(*Anim,TEXT("mode"),P.AnimationMode) ||
       !TArray<FString>{TEXT("clips"),TEXT("existing"),TEXT("none")}.Contains(P.AnimationMode) ||
       !(*Anim)->HasTypedField<EJson::Boolean>(TEXT("disable_groom_simulation"))) return false;
    P.bDisableGroom=(*Anim)->GetBoolField(TEXT("disable_groom_simulation"));
    if(P.AnimationMode==TEXT("clips"))
    {
        if(!(*Anim)->TryGetObjectField(TEXT("clips"),Clips) || (*Clips)->Values.Num()!=5) return false;
        for(const TCHAR* State:{TEXT("idle"),TEXT("forward"),TEXT("backward"),TEXT("left"),TEXT("right")})
        {FString Path;if(!Text(*Clips,State,Path) || !Path.StartsWith(TEXT("/"))) return false;P.Clips.Add(Path);}
    }
    const TArray<TSharedPtr<FJsonValue>>* Mounts;
    if(!P.Document->TryGetArrayField(TEXT("mounts"),Mounts)) return false;
    TSet<FString> Seen;
    for(const auto& M:*Mounts)
    {
        const TSharedPtr<FJsonObject>* O;FString Virtual,Directory;
        if(!M->TryGetObject(O) || !Text(*O,TEXT("virtual"),Virtual) || !Text(*O,TEXT("directory"),Directory) ||
           !Virtual.StartsWith(TEXT("/")) || !Virtual.EndsWith(TEXT("/")) || Virtual.Contains(TEXT("..")) ||
           Virtual.StartsWith(TEXT("/Engine/")) || Virtual.StartsWith(TEXT("/EmbodiedResearch/")) || Seen.Contains(Virtual)) return false;
        Seen.Add(Virtual);
    }
    const TArray<TSharedPtr<FJsonValue>>* Pieces;
    if(!(*W)->TryGetArrayField(TEXT("pieces"),Pieces) || Pieces->Num()>10000) return false;
    for(const auto& Piece:*Pieces)
    {
        const TSharedPtr<FJsonObject>* O;FVector V;FString Shape,Material;
        if(!Piece->TryGetObject(O) || !Vector(*O,TEXT("position_cm"),V) || !Vector(*O,TEXT("size_cm"),V,.01,1e6) ||
           !Vector(*O,TEXT("rotation_deg"),V,-360,360) || !Text(*O,TEXT("shape"),Shape) ||
           !TArray<FString>{TEXT("Cube"),TEXT("Cylinder"),TEXT("Sphere")}.Contains(Shape) || !Text(*O,TEXT("material"),Material) ||
           !(*O)->HasTypedField<EJson::Boolean>(TEXT("collision"))) return false;
    }
    Error.Empty();return true;
}
