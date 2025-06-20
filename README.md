# HorridDeobfuscator

> [!IMPORTANT]
> This tool deobfuscates *class names* by comparing them with a previous, unobfuscated version. It will not deobfuscate other symbols (such as method names) or decompile code. If you do not have an unobfuscated version of your game, this will not help you.

A class name deobfuscator for IL2CPP games, similar to [Beebyte-Deobfuscator](https://github.com/OsOmE1/Beebyte-Deobfuscator). It takes in an on obfuscated dump.cs file and an earlier unobfuscated version, and uses differential analysis to compare classes and generate a mapping of unobfuscated class names to obfuscated ones. It is lightning-fast, able to **deobfuscate an entire game (9000 classes) in 
This is taken from [Il2cppWorkshop](https://github.com/HorridModz/Il2cppWorkshop), a super shitty and unfinished "modding megatool" that ended up having class name deobfuscation as its main feature (the other usable features, including my glorious mod menu installer, are also sitting on my computer as projects I haven't ever gotten around to publishing).

I wrote this 3 years ago, and am finally posting it since there aren't many deobfuscators out there and a lot of people have asked me for it.
~~The code is attrocious, the program is full of bugs, and the code demonstrates a laughably pathetic and mistake-ridden attempt by a complete idiot to understand C# (such as mistaking compiler-generated classes for "shared" (???) classes, thinking that access modifiers are parts of data types, and referring to nested types like Dict<string, int> as "data type groups"). The deobfuscation itself is also not very well-done - for example, the algorithm used to compare the similarity of objects assigns arbitrary and untested weights to measures like class size and data types of methods.~~

After hours upon hours of cringing at my horrendous old code, I have done a pretty thorough job fixing it up. It still has a lot of inefficiencies and perhaps some bugs, but pretty much all of it has been rewritten at one point or another, and I have made many optimizations and improvements.

# Usage

> [!WARNING]
> As is described above, this tool is built on old, crappy code that I made years ago and may still contain bugs. If it doesn't work, feel free to let me know what's going on (you can file an issue on this repository or reach out on Discord - `@horridmodz`. Also, the tool may produce false positives in its deobfuscation mappings, or fail to find the right class. Lastly, the tool often gives multiple results if it finds multiple similar classes (especially for smaller classes), which will require you to find the correct one either by trial and error or by manual inspection (there are sometimes obvious things - unique method signatures, default values in parameters, rarely used data types, string constants... which can make this task very easy). While this tool can suffice on its own, it is best used as a supplementary tool for those who already understand how to deobfuscate classes manually.

In order to deobfuscate class names, you need an unobfuscated version of the game. Once you have obtained your
unobfuscated and current version, dump both with [Il2cppDumper](https://github.com/Perfare/Il2CppDumper)
or [Il2cppDumper-GUI](https://github.com/AndnixSH/Il2CppDumper-GUI). If you know the pattern that obfuscated class names
follow, you can provide the tool a regex. This will greatly help with deobfuscation accuracy by removing non-obfuscated
ames from the pool of potential matches. For example, Pixel Gun 3D's regex is
`'[丕世东专丛三丐丄丗丈七丒上丘丟丁丝业丏一丙丌丂不下与万且丅丑丞丆年月日년월일시분초時时分秒]+'`; any classes in the
obfuscated dump.cs that do not follow this naming pattern will be ignored.

### Running the Tool

HorridDeobfuscator is available as an exe via PyInstaller - TODO: LINK
If you would like to make changes or improvements, feel free to edit the code and either run from python or
re-build using pyinstaller (`pyinstaller main.py --onefile`). Most of the logic is in `src\Utils.py`, while the driver code is in
`main.py`. The code isn't very user-friendly, though.

> [!IMOPORTANT]
> By default, this tool groups classes and other types by modifiers: public static classes will only be
> compared with other public static classes, private sealed with private sealed, etc. This is a tradeoff - it makes
> things much faster, but may sacrifice accuracy in the rare case that a class's modifiers are changed. This can be
> disabled with the`group_by_modifiers` setting. If it is disabled, class modifiers will not be considered at all (_they should be, but are not implemented at the moment_).

### Settings

This tool is highly customizable via its `config.json` file, which will be created in the same directory as the exe or
python script (if it is not found, a new one will be created with default settings).

Here are all of the settings you can change:

- **unobfuscated_dumpcs**: The file path to your unobfuscated `dump.cs` file (make sure to escape backslashes). If this is left blank, you will be prompted to supply it every time you run the tool.
left blank
- **output_file**: The file path for your output to be written to (make sure to escape backslashes). If this is left blank, you will be prompted to supply it every time you run the tool.
- **output_json**: Enable to have the tool output the data in json format instead of text
- **deobfuscate_classes**: Whether to deobfuscate classes
- **deobfuscate_structs**: Whether to deobfuscate structs
- **deobfuscate_classes**: Whether to deobfuscate interfaces
- **deobfuscate_enums**: Whether to deobfuscate enums
- **include_scores**: Whether to include similarility scores in the generated deobfuscation mappings. This can be helpful with discerning which class to visit first if you get multiple matches (e.g. if one has a score of 80% and one has a score of 100, you should check the latter first). But it can also get annoying, especially when there's a lot of matches for a class. <br>
- - With
  include_scores: `BonusBankViewItem.UIFiller = ['万丐丅丝且与下七丙.丙丟丝丞万丘三丞丕'] (similarity = 100%)` <br>
- - Without include_scores: `BonusBankViewItem.UIFiller = ['万丐丅丝且与下七丙.丙丟丝丞万丘三丞丕']`
- **trustnames**: Whether to assume that two classes or namespaces with the same name in each version are indeed the same. This should be enabled unless the game purposely scrambles names as a method of obfuscation.

> [!NOTE]
> To reset settings to default, simply delete the `config.json` file.

#### Deobfuscation Weights

You can also modify the weights of certain things, such as method data types and size of class (these weights are used to assign different importance to different factors; for example, the class's access modifiers are more important than individual methods). Here are all of these weights:

> [!IMPORTANT]
> These weights were set by me, based on intuition. Deobfuscation is sort of a black box, unless you're willing to manually generate a big list of _correct_ unobfuscated-obfuscated mappings to test again, and that's a lot of work. I honestly have no idea if these weights are correct or make any sense; they were arrived by intuition and a bit of trial and error. Feel free to experiment with them!

- **methodweight**: The weight per each method in a class (note that it must be an exact match, including params)
- **fieldweight**: The weight per each field in a class
- **propertyweight**: The weight per each property in a class
- **sizeweight**: The weight for the size (defined by the amount) of the overall class. Each difference in size by _sizebenchmark_ items will cause a penalty of _sizeweight_ points.
- **sizebenchmark**: Each difference in size by this amount will cause a penalty. This exists to provide greater precision in size comparison - a difference in 1 item is negligible, but a difference in 5 items is more notable. Each difference in size by _sizebenchmark_ items will cause a penalty of _sizeweight_ points (dropping the remainder).

**Example for size**: unobfuscated = 5 methods, 2 properties, and 10 fields -> size = **17**. Obfuscated = 4 methods, 1 property, and 3 fields -> size == **8**. <br>
If `sizebenchmark` is **4** and `sizeweight` is `1`: There is a difference of 9 items between the two classes, so the penalty is incurred 9/4 (dropping the remainder), or **2** times, leading to a total penalty of **2**.

> [!NOTE]
> This tool currently checks a depressing amount of factors, and as such, it has an underwhelming amount of customizable weights. Note that classes must match for _all modifiers_ (sealed, abstract, visibility, etc.) if _groupbymodifiers_ is true; if not, class modifiers will not be considered (_they should be, but are not implemented at the moment_).

# Todo

- Implement option to dynamically adjust tolerance in order to refine to as little results as possible (il2cppworkshop
- technique); also make it so it can adjust up until at least one result is found
- Replace class modifiers with more specific checks, each with its own weight (sealed, abstract, visibility, etc.)
- Add has generics check (must match)
- Implement proportional weighing for class modifiers, size, and hasgenerics
- Compare methods, fields, and properties using regex (PG3D Deobfuscation Util technique) for greater accuracy (will allow things like string literals and default values)
