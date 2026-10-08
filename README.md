# Card iOS build

Windows Unity exports the Xcode project. Codemagic compiles it on a Mac M2 into an unsigned device IPA. Sideloadly signs and installs that IPA on a personal iPhone.

Required repository files:
- codemagic.yaml
- ios-export.zip (the ZIP root contains Unity-iPhone.xcodeproj)

In Codemagic, use a Personal account and run workflow unity-ios-unsigned. Download Card-unsigned.ipa from Artifacts after a successful build.

No Unity or Apple account credentials are required in this repository or the cloud workflow.
