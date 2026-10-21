using UnrealBuildTool;
using System.Collections.Generic;
public class ResearchHarnessTarget : TargetRules
{
    public ResearchHarnessTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("ResearchHarness");
    }
}
