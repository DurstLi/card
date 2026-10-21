"""Prepare the existing Xcode export for a signed startup diagnostic build."""
import pathlib
import plistlib
import sys

root = pathlib.Path(sys.argv[1])
plist_path = root / "Info.plist"
with plist_path.open("rb") as stream:
    info = plistlib.load(stream)

# The project allows both landscape orientations. The Windows export omitted them.
orientations = ["UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"]
info["UISupportedInterfaceOrientations"] = orientations
info["UISupportedInterfaceOrientations~ipad"] = orientations
info["UIFileSharingEnabled"] = True
info["LSSupportsOpeningDocumentsInPlace"] = True
info["CFBundleVersion"] = "2"
with plist_path.open("wb") as stream:
    plistlib.dump(info, stream, sort_keys=False)

source_path = root / "Classes" / "UnityAppController.mm"
source = source_path.read_text(encoding="utf-8-sig")
old_handler = '''bool LogToNSLogHandler(LogType logType, const char* log, va_list list)
{
    NSLogv([NSString stringWithUTF8String: log], list);
    return true;
}'''
new_handler = '''// CARD_STARTUP_DIAGNOSTICS: local file only; no remote log upload.
static NSObject* CardDiagnosticLock()
{
    static NSObject* lock = [NSObject new];
    return lock;
}

static NSString* CardDiagnosticPath()
{
    return [NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0]
        stringByAppendingPathComponent:@"Card-startup.log"];
}

static void CardWriteDiagnostic(NSString* message)
{
    @synchronized(CardDiagnosticLock())
    {
        const char* path = [CardDiagnosticPath() fileSystemRepresentation];
        FILE* file = fopen(path, "ab");
        if (!file) return;
        fseek(file, 0, SEEK_END);
        // Bound log size while retaining the startup and first error messages.
        if (ftell(file) < 4 * 1024 * 1024)
        {
            NSString* line = [NSString stringWithFormat:@"%@ %@\\n", [NSDate date], message];
            NSData* data = [line dataUsingEncoding:NSUTF8StringEncoding];
            fwrite(data.bytes, 1, data.length, file);
            fflush(file);
        }
        fclose(file);
    }
}

static void CardPrepareDiagnosticLog()
{
    // Keep the most recent launch and its predecessor, even if the app exits immediately.
    NSFileManager* manager = [NSFileManager defaultManager];
    NSString* path = CardDiagnosticPath();
    NSString* previous = [path stringByAppendingString:@".previous"];
    [manager removeItemAtPath:previous error:NULL];
    if ([manager fileExistsAtPath:path]) [manager moveItemAtPath:path toPath:previous error:NULL];
    CardWriteDiagnostic(@"Card diagnostic build 2: native startup begins");
    CardWriteDiagnostic([NSString stringWithFormat:@"iOS %@, app %@ (%@)",
        [UIDevice currentDevice].systemVersion,
        [[NSBundle mainBundle] objectForInfoDictionaryKey:@"CFBundleShortVersionString"],
        [[NSBundle mainBundle] objectForInfoDictionaryKey:@"CFBundleVersion"]]);
    NSString* dataRoot = [[NSBundle mainBundle].bundlePath stringByAppendingPathComponent:@"Data"];
    for (NSString* relative in @[@"globalgamemanagers", @"boot.config", @"Managed/Metadata/global-metadata.dat"])
    {
        NSDictionary* attributes = [manager attributesOfItemAtPath:[dataRoot stringByAppendingPathComponent:relative] error:NULL];
        CardWriteDiagnostic([NSString stringWithFormat:@"Data/%@: %@ bytes", relative, attributes[NSFileSize] ?: @"MISSING"]);
    }
}

bool LogToNSLogHandler(LogType logType, const char* log, va_list list)
{
    va_list copy;
    va_copy(copy, list);
    NSString* message = [[NSString alloc] initWithFormat:[NSString stringWithUTF8String:log] arguments:copy];
    va_end(copy);
    CardWriteDiagnostic(message);
    NSLogv([NSString stringWithUTF8String: log], list);
    return true;
}'''

if "// CARD_STARTUP_DIAGNOSTICS:" not in source:
    if source.count(old_handler) != 1:
        raise RuntimeError("Unexpected Unity logging handler; refusing to patch")
    source = source.replace(old_handler, new_handler)
    entry = "void UnityInitTrampoline()\n{\n"
    if source.count(entry) != 1:
        raise RuntimeError("Unexpected UnityInitTrampoline; refusing to patch")
    source = source.replace(entry, entry + "    CardPrepareDiagnosticLog();\n")
    source = "#include <cstdio>\n" + source
source = source.replace("Card diagnostic build 1: native startup begins",
                        "Card diagnostic build 2: native startup begins")

# Stage markers still identify the failing initialization call when Unity's own
# message is emitted outside its logging callback or hidden by unified logging.
declaration = 'extern "C" void CardDiagnosticStage(const char* stage);\n'
stage_function = '''extern "C" void CardDiagnosticStage(const char* stage)
{
    CardWriteDiagnostic([@"STAGE " stringByAppendingString:[NSString stringWithUTF8String:stage]]);
}

'''
if 'extern "C" void CardDiagnosticStage(const char* stage)\n{' not in source:
    source = source.replace("bool LogToNSLogHandler(", stage_function + "bool LogToNSLogHandler(", 1)
if declaration not in source:
    source = declaration + source


def instrument(text, call, stage):
    before = f'    CardDiagnosticStage("{stage}: begin");\n'
    after = f'\n    CardDiagnosticStage("{stage}: complete");'
    if before in text:
        return text
    needle = "    " + call
    if text.count(needle) != 1:
        raise RuntimeError("Unexpected Unity startup call; refusing to patch: " + call)
    return text.replace(needle, before + needle + after)


for call, stage in [
    ("UnityInitApplicationNoGraphics(UnityDataBundleDir());", "engine-no-graphics"),
    ("UnityInitApplicationGraphics();", "graphics"),
    ("UnityLoadApplication();", "first-scene"),
]:
    source = instrument(source, call, stage)

main_path = root / "Classes" / "main.mm"
main_source = main_path.read_text(encoding="utf-8-sig")
if declaration not in main_source:
    main_source = declaration + main_source
main_source = instrument(main_source, "UnityInitRuntime(argc, argv);", "native-runtime")
main_source = instrument(main_source, "RegisterFeatures();", "register-features")

source_path.write_text(source, encoding="utf-8")
main_path.write_text(main_source, encoding="utf-8")

print("Diagnostic build 2 prepared: landscape, native startup stages, Documents/Card-startup.log")
