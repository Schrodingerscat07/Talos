using UnrealBuildTool;
using System.Collections.Generic;
public class ResearchHarnessEditorTarget : TargetRules
{
    public ResearchHarnessEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("ResearchHarness");
    }
}
