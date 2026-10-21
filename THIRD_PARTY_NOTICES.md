# Third-party dependencies and assets

The root MIT License applies to the Talos-authored source and documentation in this repository. It does not relicense separately obtained dependencies or content. No Unreal Engine source/binaries, mannequin/MetaHuman assets, personal character model, derived animation assets or recorded avatar images are distributed here.

| Dependency/content | Use | Distribution boundary |
| --- | --- | --- |
| Unreal Engine 5.8.3 and its editor plugins | Build, rendering, collision, asset import and retargeting | Install separately through Epic; its own license applies |
| Epic mannequin/template assets | Example character and supplied idle/walk clips | Referenced by package path; obtain with the supported engine installation |
| MetaHuman/Bob content and derived retargeted clips | Optional reference avatar | Private external content/local generated assets; excluded from Git and handoff ZIPs |
| Other Unreal or Blender characters, maps and motions | User-selected research inputs | Obtain permission and preserve the relevant licenses and attribution |
| Python, build toolchain, optional Chrome/Node | Client, compilation and local validation | Install separately; no vendored runtime is included |

Blender is an optional authoring/import workflow, not a bundled runtime dependency. Its software license does not establish ownership or distribution rights for imported artwork or motion datasets. Asset names and virtual paths in example profiles are references, not copies of those assets.

Researchers must preserve the licenses/attribution of any additional code, model weights, datasets or assets they introduce. Generated recordings, derived assets, local source archives and machine configuration remain outside Git by default.
