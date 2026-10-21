using UnrealBuildTool;

public class EmbodiedResearch : ModuleRules
{
    public EmbodiedResearch(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "HTTPServer", "Json" });
        PrivateDependencyModuleNames.AddRange(new[] { "RenderCore", "RHI", "ImageWrapper", "Sockets" });
    }
}
