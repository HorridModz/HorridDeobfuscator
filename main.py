import os
import sys
import time
import warnings
from typing import Callable
import json
from deepmerge import always_merger
# Tkinter for file open dialog
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory, asksaveasfilename
from src.Utils import *

Tk().withdraw()


def read_file(path):
    file = open(path, "r")
    try:
        return file.read()
    except UnicodeDecodeError:
        try:
            file = open(path, "r", encoding="utf8")
            return file.read()
        except UnicodeDecodeError:
            try:
                file = open(path, "r", encoding="utf16")
                return file.read()
            except UnicodeDecodeError:
                file = open(path, "r", encoding="utf32")
                return file.read()
        finally:
            file.close()


def deobfuscateclassnames(unobfuscateddumpcs, obfuscateddumpcs, include_scores=True, classes=True,
                          structs=True, interfaces=True, enums=True, obfuscation_regex=None,
                          tolerance: int | float = 80, trust_names: bool = True, groupbymodifiers: bool = True,
                          basetypes_mustbesameamount: bool = False):
    deobfuscate_typekinds: set[str] = set()
    if classes:
        deobfuscate_typekinds.add("class")
    if structs:
        deobfuscate_typekinds.add("structs")
    if interfaces:
        deobfuscate_typekinds.add("interface")
    if enums:
        deobfuscate_typekinds.add("enum")
    starttime = time.time()
    print("Compiling type models...", end=" ")
    dumpcs = read_file(unobfuscateddumpcs)
    fulltypes = getfulltypes(dumpcs, False)
    fullclasses = list(filter(lambda thistype: get_typekind(thistype) in deobfuscate_typekinds, fulltypes))
    unobfuscated = gettypes(fullclasses)
    dumpcs = read_file(obfuscateddumpcs)
    fulltypes = getfulltypes(dumpcs, False)
    fullclasses = list(filter(lambda thistype: get_typekind(thistype) in deobfuscate_typekinds, fulltypes))
    obfuscated = gettypes(fullclasses)
    print("Done")
    results = {}
    obfuscated_byname = set(thisobfuscated["FullName"] for thisobfuscated in obfuscated)
    obfuscated_namespaces = set(thisobfuscated["Namespace"] for thisobfuscated in obfuscated)
    obfuscated_roottypes = set(getroottype(thisobfuscated["Name"]) for thisobfuscated in obfuscated)
    for i, thisunobfuscated in enumerate(unobfuscated):
        if i % 20 == 0:
            print(f"{i}/{len(unobfuscated)} classes deobfuscated")
        results[thisunobfuscated["FullName"]] = []
        if trust_names and thisunobfuscated["FullName"] in obfuscated_byname:
            # Class is not obfuscated; no need to search for it
            results[thisunobfuscated["FullName"]].append(thisunobfuscated["FullName"])
            continue
        for thisobfuscated in obfuscated:
            # noinspection IncorrectFormatting
            if trust_names and thisunobfuscated["Namespace"] in obfuscated_namespaces and\
             thisunobfuscated["Namespace"] != thisobfuscated["Namespace"]:
                continue
            # noinspection IncorrectFormatting
            if trust_names and getroottype(thisunobfuscated["Name"]) in obfuscated_roottypes and\
             getroottype(thisunobfuscated["Name"]) != getroottype(thisobfuscated["Name"]):
                continue
            if thisunobfuscated.get("TypeKind") != thisobfuscated.get("TypeKind"):
                continue
            if groupbymodifiers and thisunobfuscated.get("Modifiers") != thisobfuscated.get("Modifiers"):
                continue
            if thisunobfuscated.get("IsCompilerGenerated") != thisobfuscated.get("IsCompilerGenerated"):
                continue
            if not compare_basetypes(thisunobfuscated["BaseTypes"], thisobfuscated["BaseTypes"],
                                     basetypes_mustbesameamount, trust_names, obfuscation_regex):
                continue
            if not compare_namespaces(thisunobfuscated["Namespace"], thisobfuscated["Namespace"], trust_names,
                                      obfuscation_regex):
                continue
            if not compare_identifiers(thisunobfuscated["Name"], thisobfuscated["Name"], trust_names,
                                       obfuscation_regex):
                continue
            score = compare_typemodels(thisunobfuscated["TypeModel"], thisobfuscated["TypeModel"],
                                       domodifiers=False)
            if score >= tolerance or (trust_names and thisunobfuscated["Name"] == thisobfuscated["Name"]):
                # If type meets tolerance score or has same name (though namespace cannot be guaranteed if it's
                # obfuscated), add to matches
                results[thisunobfuscated["FullName"]].append(
                        f"{thisobfuscated['FullName']} (similarity = {score:.0f}%)" if include_scores else
                        thisobfuscated['FullName'])
    print(f"All class names deobfuscated in {time.time() - starttime} seconds.")
    return results


def _loadconfig() -> dict:
    if os.path.exists(_configpath):
        with open(_configpath, "r") as f:
            return json.load(f)
    else:
        """
        config.json does not exist, fall back to hardcoded defaults
        """
        return _defaults


def _writeconfig(config: dict) -> None:
    with open(_configpath, "w") as f:
        json.dump(config, f, indent=2)


def _config(**kwargs) -> dict:
    """
    This is a neat trick that lets me generate a dictionary with my config just by calling
    this function with the options as arguments!
    """
    return kwargs


def fileselect_dialog(dialog_func: Callable, **kwargs) -> str:
    """
    Only use for tkinter's askopenfilename, askdirectory, and asksaveasfilename
    """
    if dialog_func not in {askopenfilename, askdirectory, asksaveasfilename}:
        raise ValueError("Unsupported file dialog function")
    path = dialog_func(**kwargs)
    if path == "":
        # File dialog canceled
        sys.exit()
    return path

if getattr(sys, 'frozen', False):
    # Running as pyinstaller executable - find real location of exe
    _configpath = os.path.join(os.path.dirname(sys.executable), "config.json")
else:
    # Running as pyton script
    _configpath = os.path.join(os.path.dirname(__file__), "config.json")

if __name__ == "__main__":
    _defaults = _config(unobfuscated_dumpcs="", output_file="", output_json=False, deobfuscate_classes=True,
                        deobfuscate_structs=True, deobfuscate_interfaces=True, deobfuscate_enums=True,
                        include_scores=True)
    _defaults["Deobfuscation"] = _config(trust_names=True, obfuscation_regex=None, match_tolerance=80,
                                         groupbymodifiers=True,
                                         basetypes_mustbesameamount=False)
    _defaults["Deobfuscation"]["Weights"] = _config(method_weight=3,
                                                    field_weight=2, property_weight=5, size_weight=0.8,
                                                    size_benchmark=3)
    if not os.path.exists(_configpath):
        try:
            _writeconfig(_defaults)
            print(f"Created config.json file at {_configpath}")
        except Exception as e:
            warnings.warn(f"Failed to create config.json at {_configpath}: {e}")
    # Any missing options in config will be set to default (recursive)
    try:
        _settings = always_merger.merge(_defaults.copy(), _loadconfig())
    except json.decoder.JSONDecodeError:
        warnings.warn("Failed to load config.json due to malformed content. Using defaults.")
        _settings = _defaults.copy()

    unobfuscated_dumpcs = _settings["unobfuscated_dumpcs"]
    output_file = _settings["output_file"]
    output_json = _settings["output_json"]
    include_scores = _settings["include_scores"]
    trust_names = _settings["Deobfuscation"]["trust_names"]
    obfuscation_regex = _settings["Deobfuscation"]["obfuscation_regex"]
    tolerance = _settings["Deobfuscation"]["match_tolerance"]
    groupbymodifiers = _settings["Deobfuscation"]["groupbymodifiers"]
    basetypes_mustbesameamount = _settings["Deobfuscation"]["basetypes_mustbesameamount"]

    # obfuscated_dumpcs = input("Enter the path to the dump.cs file you would like to deobfuscate: ").strip('"')
    obfuscated_dumpcs = fileselect_dialog(askopenfilename,
                                          title="Select the OBFUSCATED dump.cs file that you would like to deobfuscate",
                                          filetypes=[("C# source file (*.cs)", "*.cs"), ("All Files", "*.*")])
    if unobfuscated_dumpcs is None or  unobfuscated_dumpcs == "" or unobfuscated_dumpcs.isspace():
        # unobfuscated_dumpcs = input("\nEnter the path to your UNOBFUSCATED dump.cs file: ").strip('"')
        unobfuscated_dumpcs = fileselect_dialog(askopenfilename, title="Select your UNOBFUSCATED dump.cs file",
                                                filetypes=[("C# source file (*.cs)", "*.cs"), ("All Files", "*.*")])
    else:
        print(f"Using unobfuscated dumpcs from config: {unobfuscated_dumpcs }")
    if output_file is None or  output_file == "" or output_file.isspace():
        # output_file = input("Enter the file path you want deobfuscation output written to: ").strip('"')
        output_file = fileselect_dialog(asksaveasfilename, title="Select file for deobfuscation output",
                                        filetypes=[("Normal text file (*.txt)", "*.txt"),
                                                   ("JSON file (*.json)", "*.json"), ("All Files", "*.*")])
    else:
        print(f"Will write to output file from config: {output_file}")
    if obfuscation_regex is not None and obfuscation_regex != "" and not obfuscation_regex.isspace():
        print(f"Using obfuscation regex from config: {obfuscation_regex}")

    results = deobfuscateclassnames(unobfuscated_dumpcs, obfuscated_dumpcs, include_scores,
                                    _settings["deobfuscate_classes"], _settings["deobfuscate_structs"],
                                    _settings["deobfuscate_interfaces"], _settings["deobfuscate_enums"],
                                    obfuscation_regex, tolerance, trust_names, groupbymodifiers,
                                    basetypes_mustbesameamount)
    print("Writing to output file...")
    if output_json:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
    else:
        formatted = ""
        for unobfuscated, matches in results.items():
            formatted += f"{unobfuscated} = {matches}\n"
        with open(output_file, "w") as f:
            f.write(formatted)

# TODO: Can we get rid of all unobfuscated names in obfuscated dump.cs beforehand? Do checks to see if we have any
#  by-name matches; after that anything unobfuscated which doesn't have a by-name match can be removed since it
#  doesn't have a match in unobfuscated
# TODO: Implement option to adjust tolerance in order to refine to as little results as possible (il2cppworkshop
#  technique); also make it so it can adjust up until at least one result is found
# TODO: Replace class modifiers with more specific checks, each with its own weight (sealed, abstract, visibility,
#  etc.) - implement is_sealed etc.
# TODO: Add hasgenerics (must match)
# TODO: Implement proportional weighing for class modifiers and size and hasgenerics
