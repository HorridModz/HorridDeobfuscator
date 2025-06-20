import re
from functools import cache
from typing import Optional
from dataclasses import dataclass


_typenamereplace = "NON_BUILTIN_TYPE"
_typekinds = {"class", "struct", "enum", "interface"}
_access_modifiers = {"public", "internal", "private", "protected", "protected internal", "private protected"}
_class_modifiers = {"sealed", "abstract", "partial", "static"}
# This is not just types; it also includes modifiers as well as in, out, ref, const, readonly, args, etc.)
_builtin_types = {"abstract", "args", "bool", "byte", "const", "char", "decimal", "delegate", "double",
                  "event", "float", "int", "int16", "int32", "int64", "internal", "long", "Nullable",
                  "Object", "object", "extern", "volatile", "fixed", "virtual", "in", "out", "ref", "KeyValuePair",
                  "override", "params",
                  "predicate", "Predicate", "readonly", "ref", "sbyte", "sealed",
                  "short", "static", "String", "string", "uint", "uint16", "uint32", "uint64", "ulong", "unchecked",
                  "unsafe", "ushort", "void", "get", "set", "value", "ICollection", "IEnumerable", "IList",
                  "IEqualityComparer", "IEnumerator", "Iterator", "TResult", "TSource", "Func", "IComparer",
                  "IHashCodeProvider", "IStructuralEquatable", "IDictionary", "IDictionaryEnumerator",
                  "IStructuralComparable", "Hashmap", "Hashtable", "Action", "Func", "Array", "List", "Dictionary",
                  "ICloneable", "ISerializable", "IDeserializationCallback", "Color", "Color32", "Vector1",
                  "Vector2", "Vector3", "Quaternion"}
# Dump.cs Parsing
_isoffsetstring = "// RVA: "
_offsetprefix = "Offset: 0x"
_offsetsuffix = " VA: 0x"
_typeseparator = "// Namespace: "
_namespaceline = 1
_namespacenamestart = "// Namespace: "
_typedeclarationline = 2
_typedeclarationend = " // TypeDefIndex: "
_fieldsstart = "\t// Fields"
_propertiesstart = "\t// Properties"
_methodsstart = "\t// Methods"
_contentends = {"}", "\t// Methods", "\t// Fields", "\t// Properties"}
_genericinstmethodstart = "/* GenericInstMethod :"
_genericinstmethodend = "*/"
_fieldoffsetstart = "; // 0x"
_propertyaccessorsstart = " { "
_propertyaccessorsend = "; }"
_propertyaccessorseparator = "; "
_methodoffsetline = 1
_methodtypeline = 2
_methodparamsstart = "("
_methodparamsend = ")"
_ismethodstring = ") {"
_ispropertystring = "; }"
_isfieldstring = "; // 0x"


@dataclass
class DeobfuscationWeights:
    class_visibility_weight: int = NotImplemented
    class_is_sealed_weight: int = NotImplemented
    class_is_static_weight: int = NotImplemented
    class_is_abstract_weight: int = NotImplemented
    method_weight: int = 3 # per each method
    field_weight: int = 2 # per each field
    property_weight: int = 5 # per each property
    size_weight: float = 0.3  # per each sizebenchmark
    size_benchmark: int = 4

def substring(text, start, end=999999999999999999999):
    if start < 1:
        return text[0:end]
    else:
        return text[start - 1: end]


def readbetween(fullstr, startstr, endstr, endfromend=True):
    startpos = fullstr.find(startstr) + len(startstr)
    endpos = fullstr.rfind(endstr) if endfromend else fullstr.find(endstr)
    if startpos is None or endpos is None:
        return ""
    else:
        return fullstr[startpos:endpos]


def readafter(fullstr, startstr):
    return fullstr[fullstr.find(startstr) + len(startstr):]


def readbefore(fullstr, endstr, fromend=True):
    return fullstr[:(fullstr.rfind(endstr) + 1 if fromend else fullstr.find(endstr))]


def removeblanklines(s):
    return s.replace("\n\n", "\n")


def getfulltypes(dumpcs, getcompilergenerated=True):
    fulltypes = [f"{_typeseparator}{fulltype}" for fulltype in dumpcs.split(_typeseparator)[1:]]
    # Remove attributes and blank lines
    fulltypes = [removeattributes(removeblanklines(fulltype)) for fulltype in fulltypes]
    if not getcompilergenerated:
        fulltypes = [fulltype for fulltype in fulltypes if not is_compilergenerated(fulltype)]
    return fulltypes


def removeattributes(thistype):
    newlines = []
    for thisline in thistype.splitlines():
        if thisline.isspace() or thisline.strip()[0] != "[":
            newlines.append(thisline)
    return "\n".join(newlines)


@cache
def get_typekind(thistype):
    typekind = None
    lines = thistype.splitlines()
    words = lines[_typedeclarationline - 1].split()
    for thisword in words:
        if thisword in _typekinds:
            typekind = thisword
            break
    return typekind


@cache
def is_compilergenerated(thistype):
    return "<" in gettypename(thistype)


@cache
def get_type_modifiers(thistype):
    modifiers = ""
    lines = thistype.splitlines()
    words = lines[_typedeclarationline - 1].split()
    for thisword in words:
        if thisword in _typekinds:
            break
        modifiers = " ".join([modifiers, thisword])
    return modifiers


@cache
def gettypenamespace(thistype):
    lines = thistype.splitlines()
    thisline = lines[_namespaceline - 1]
    namespacename = readafter(thisline, _namespacenamestart)
    namespacename = namespacename.strip()
    if namespacename == "":
        return None
    return namespacename


@cache
def gettypename(thistype):
    lines = thistype.splitlines()
    words = lines[_typedeclarationline - 1].split()
    for i, thisword in enumerate(words):
        if thisword in _typekinds:
            # Next word is type name
            return words[i + 1]


@cache
def getbasetypes(thistype) -> Optional[list[str]]:
    lines = thistype.splitlines()
    thisline = lines[_typedeclarationline - 1]
    if " : " not in thisline:
        return None
    return readbetween(thisline, " : ", _typedeclarationend).split(", ")


def gettypefullname(namespace, name):
    return f"{namespace}.{name}" if namespace is not None else name

def getroottype(name):
    return name.split(".")[0]

def gettypenestinglevel(name):
    return name.count(".")


@cache
def getmethodparams(thismethod):
    method_line = thismethod.splitlines()[-1]
    paramssection = method_line[method_line.find("(") + len("("):method_line.find(")")]
    # Split params by comma - default arguments make this a big pain, because we have to make sure we are not in
    # default argument strings when we hit commas.
    params = []
    build = ""
    instring = None
    escape = False
    skipnext = False
    for letter in paramssection:
        if skipnext:
            # skip space after comma (as delimiter is ", ")
            skipnext = False
            continue

        # Handle escapes in default argument strings
        if instring and escape:
            escape = False
        elif instring and letter == "\\":
            escape = True

        # Handle default argument strings
        elif instring is None and letter in ("\"", "'"):
            instring = letter
        elif instring is not None and letter == instring:
            instring = False

        # Handle comma delimiter (if not in default argument string)
        elif instring is None and letter == ",":
            params.append(build)
            build = ""
            skipnext = True  # skip space after comma (as delimiter is ", ")
            continue
        build += letter
    if build != "":
        params.append(build)
    return params


@cache
def getmethodparamtypes(thismethod, replacenames=False):
    methodparams = getmethodparams(thismethod)
    param_types = []
    for param in methodparams:
        # Remove default parameter
        if " =" in param:
            param = param.partition(" =")[0]
        words = param.split(" ")
        if words[0] in {"params", "ref", "in", "out"}:
            words.pop(0)
        data_type = words[0]
        if replacenames:
            data_type = replacetypenames(data_type)
        param_types.append(data_type)
    return param_types


@cache
def replacetypenames(thistype):
    r"""
    Replaces any non-builtin identifiers in data types with a sentinel string, because these names will change if
    obfuscated.

    Ahh, the gloriously ugly and overcomplicated fuckery that is regex. This is basically just matching the identifiers
    with word boundaries, except they can also contain some extra characters (namely '-', '_', and '~') - these extra
    characters are valid characters for identifier names in C# (to my knowledge). In order to do this, we define our
    boundary characters in a huge character class.
    In other words, this regex is basically just "\b(?!TYPES)\w+\b" with some tweaks.
    """
    return re.sub(fr"(?<![^\s\[\]!\"#$%&'()*+.,/:;<=>?@\\^`{{|}}~])(?!{'|'.join(_builtin_types)})"
                  r"[^\s\[\]!\"#$%&'()*+.,/:;<=>?@\\^`{|}~]+", _typenamereplace, thistype)


def compare_identifiers(unobfuscated, obfuscated, trust_names: bool = True, obfuscation_regex=None):
    """
    True = may match
    False = do not match

    **Make sure first parameter is unobfuscated and second is obfuscated**

    Checks if two identifiers or namespaces may match. Compares the nesting level regardless of whether obfuscation
    regex is supplied. If obfuscation regex is supplied, detect unobfuscated pieces of the obfusacted identifier and
    compare them against the corresponding pieces in the unobfuscated identifier.

    Examples: MyClass and 丑丈丙下丂丂七丒丗.丆丝丂丕丘丐上丂一 -> False (different nesting level)
              MyClass.SubClass and 丑丈丙下丂丂七丒丗.丆丝丂丕丘丐上丂一 -> True
              MyClass.SubClass and 丑丈丙下丂丂七丒丗.Other -> False (While "MyClass" may or may not match,
                    "Subclass" and "Other" do not)
              MyClass.SubClass and 丑丈丙下丂丂七丒丗.Subclass -> True
    """
    if gettypenestinglevel(unobfuscated) != gettypenestinglevel(obfuscated):
        return False
    if trust_names and obfuscation_regex is not None:
        if not re.search(obfuscation_regex, obfuscated):
            # Name is not obfuscated, so check directly
            return unobfuscated == obfuscated
        # Check individuals parts to see if any individual parts are unobfuscated; if they are, we can check those
        # individually
        for partofunobfuscated, partofobfuscated in zip(unobfuscated.split("."), obfuscated.split(".")):
            if not re.match(obfuscation_regex, partofobfuscated) and partofunobfuscated != partofobfuscated:
                return False
    return True


@cache
def compare_namespaces(unobfuscated, obfuscated, trustnames: bool = True, obfuscatednamespaceregex=None) -> bool:
    """
    True = may match
    False = do not match

    **Make sure first parameter is unobfuscated and second is obfuscated**
    """
    if unobfuscated is None and obfuscated is None:
        return True
    elif trustnames and unobfuscated == obfuscated:
        return True
    if (unobfuscated is None) ^ (obfuscated is None):  # XOR
        # If one class is in a namespace and one class isn't, then namespaces cannot be the same
        return False
    return compare_identifiers(unobfuscated, obfuscated, trustnames, obfuscatednamespaceregex)


def compare_basetypes(unobfuscated, obfuscated, mustbesameamount: bool = False,
                      trustnames: bool = True, obfuscatednamespaceregex=None) -> bool:
    """
    True = may match
    False = do not match

    mustbesameamount: If true, they have to have to have the same amount of bases to be considered a match? If not,
    obfuscated can have more than unobfuscated (in case additional ones were added on) but not less.

    **Make sure first parameter is unobfuscated and second is obfuscated**
    """
    if unobfuscated is None and obfuscated is None:
        return True
    elif trustnames and unobfuscated == obfuscated:
        return True
    if (unobfuscated is None) ^ (obfuscated is None):  # XOR
        return False
    if len(unobfuscated) > len(obfuscated) or len(obfuscated) > len(unobfuscated) and mustbesameamount:
        return False  # Different number of base types
    for unobfuscated_basetype, obfuscated_basetype in zip(unobfuscated, obfuscated):
        if not compare_identifiers(unobfuscated_basetype, obfuscated_basetype, trustnames, obfuscatednamespaceregex):
            return False
    return True


@cache
def getmethodtype(thismethod, replacenames=False):
    lines = thismethod.splitlines()
    thisline = lines[_methodtypeline - 1]
    thisline = substring(thisline, 0, thisline.find(_methodparamsstart))
    methodtype = readbefore(thisline, _methodparamsstart)
    methodtype = methodtype.strip()
    words = methodtype.split()
    if len(words) > 0:
        del words[len(words) - 1]
    methodtype = " ".join(words)
    if replacenames:
        methodtype = replacetypenames(methodtype)
    return methodtype


@cache
def getmethodname(thismethod):
    lines = thismethod.splitlines()
    thisline = lines[_methodtypeline - 1]
    thisline = substring(thisline, 0, thisline.find(_methodparamsstart))
    methodname = readbefore(thisline, _methodparamsstart)
    methodname = methodname.strip()
    words = methodname.split()
    methodname = words[len(words) - 1]
    return methodname


@cache
def getmethodoffset(thismethod):
    lines = thismethod.splitlines()
    thisline = lines[_methodoffsetline - 1]
    methodoffset = readbetween(thisline, _offsetprefix, _offsetsuffix)
    return methodoffset


def removegenericinstmethods(fullmethods):
    lines = fullmethods.splitlines()
    newlines = []
    ingenericinst = False
    for thisline in lines:
        if thisline == _genericinstmethodstart:
            ingenericinst = True
        else:
            if (thisline == _genericinstmethodend) and ingenericinst:
                ingenericinst = False
            else:
                if not ingenericinst:
                    newlines.append(thisline)
    return newlines


@cache
def getfullmethods(thistype) -> str:
    if "\n\t// Methods\n" not in thistype:
        return ""
    return thistype[thistype.find("\n\t// Methods\n") + len("\n\t// Methods"):thistype.find("\n}")]


@cache
def getmethodslist(fullmethods):
    lines = removegenericinstmethods(fullmethods)
    methods = set()
    build = []
    ismethod = False
    for line in lines:
        if ismethod and line == "":
            ismethod = False
            continue
        if not ismethod and line != "":
            build.append(line)
        if ("(" in line and (line.endswith(")") or line.endswith(" { }"))) and not ismethod:
            methods.add("\n".join(build))
            build = []
            ismethod = True  # Set this flag to skip future lines until we hit a blank line and begin next method
    return methods


@cache
def getmethods(methodslist):
    if type(methodslist) == str:  # got full methods, not methods list - so convert to methods list
        methodslist = getmethodslist(methodslist)
    global methods
    methods = []
    for thismethod in methodslist:
        thismethoddata = {"Name":       getmethodname(thismethod), "Type": getmethodtype(thismethod),
                          "Content":    thismethod, "Offset": getmethodoffset(thismethod),
                          "Params":     getmethodparams(thismethod), "ParamTypes": getmethodparamtypes(thismethod), }
        methods.append(thismethoddata)
    return methods


@cache
def getfieldoffset(thisfield):
    fieldoffset = readafter(thisfield, _fieldoffsetstart)
    return fieldoffset


@cache
def getfieldtype(thisfield, replacenames=False):
    thisfield = substring(thisfield, 0, thisfield.find(_fieldoffsetstart))
    fieldtype = readbefore(thisfield, _fieldoffsetstart)
    fieldtype = fieldtype.strip()
    words = fieldtype.split()
    if len(words) > 0:
        del words[len(words) - 1]
    fieldtype = " ".join(words)
    if replacenames:
        fieldtype = replacetypenames(fieldtype)
    return fieldtype


@cache
def getfieldname(thisfield):
    thisfield = substring(thisfield, 0, thisfield.find(_fieldoffsetstart))
    fieldname = readbefore(thisfield, _fieldoffsetstart)
    fieldname = fieldname.strip()
    words = fieldname.split()
    fieldname = words[len(words) - 1]
    return fieldname


@cache
def getfieldslist(fullfields):
    lines = fullfields.splitlines()
    global fields
    fields = []
    for thisline in lines:
        if _fieldoffsetstart in thisline:
            fields.append(thisline)
    return fields


@cache
def getfields(fieldslist):
    if type(fieldslist) == str:  # got full fields, not fields list - so convert to fields list
        fieldslist = getfieldslist(fieldslist)
    global fields
    fields = []
    for thisfield in fieldslist:
        thisfielddata = {"Name":   getfieldname(thisfield), "Type": getfieldtype(thisfield), "Content": thisfield,
                         "Offset": getfieldoffset(thisfield), }
        fields.append(thisfielddata)
    return fields


def getfieldsdict(fields):
    fieldsdict = {}
    for thisfield in fields:
        fieldsdict[thisfield["Name"]] = thisfield
    return fieldsdict


@cache
def getfullfields(thistype):
    lines = thistype.splitlines()
    if _fieldsstart in lines:
        fullfields = ""
        i = lines.index(_fieldsstart) + 1
        thisitem = lines[i - 1].strip()
        fullfields = f"{fullfields}\n{thisitem}"
        i = i + 1
        thisitem = lines[i - 1].strip()
        i = i + 1
        while not ((thisitem in _contentends) or i > (len(lines) - 1)):
            i = i + 1
            if not (thisitem.isspace()):
                fullfields = f"{fullfields}\n{thisitem}"
            thisitem = lines[i - 1].strip()
    else:
        fullfields = ""
    return fullfields


@cache
def getfullproperties(thistype):
    lines = thistype.splitlines()
    if _propertiesstart in lines:
        fullproperties = ""
        i = lines.index(_propertiesstart) + 1
        thisitem = lines[i - 1].strip()
        fullproperties = f"{fullproperties}\n{thisitem}"
        i = i + 1
        thisitem = lines[i - 1].strip()
        i = i + 1
        while not ((thisitem in _contentends) or i > (len(lines) - 1)):
            i = i + 1
            if not (thisitem.isspace()):
                fullproperties = f"{fullproperties}\n{thisitem}"
            thisitem = lines[i - 1].strip()
    else:
        fullproperties = ""
    return fullproperties


@cache
def getpropertytype(thisproperty, replacenames=False):
    thisproperty = substring(thisproperty, 0, thisproperty.find(_propertyaccessorsstart))
    propertytype = readbefore(thisproperty, _propertyaccessorsstart)
    propertytype = propertytype.strip()
    words = propertytype.split()
    if len(words) > 0:
        del words[-1]
    propertytype = " ".join(words)
    if replacenames:
        propertytype = replacetypenames(propertytype)
    return propertytype


@cache
def getpropertyaccessors(thisproperty):
    return readbetween(thisproperty, _propertyaccessorsstart, _propertyaccessorsend).strip().split(
            _propertyaccessorseparator)


@cache
def getpropertyname(thisproperty):
    words = readbefore(thisproperty, _propertyaccessorsstart).split()
    return words[-1]


@cache
def getpropertieslist(fullproperties):
    global properties
    lines = fullproperties.splitlines()
    properties = []
    for thisline in lines:
        if _propertyaccessorsstart in thisline:
            properties.append(thisline)
    return properties


@cache
def getproperties(propertieslist):
    if type(propertieslist) == str:  # got full properties, not properties list - so convert to properties list
        propertieslist = getpropertieslist(propertieslist)
    global properties
    properties = []
    for thisproperty in propertieslist:
        thispropertydata = {"Name":    getpropertyname(thisproperty), "Type": getpropertytype(thisproperty),
                            "Content": thisproperty, "Accessors": getpropertyaccessors(thisproperty)}
        properties.append(thispropertydata)
    return properties


def getpropertiesdict(properties):
    propertiesdict = {}
    for thisproperty in properties:
        propertiesdict[thisproperty["Name"]] = thisproperty
    return propertiesdict


def gettypes(fulltypes):
    types = []
    for thisfulltype in fulltypes:
        types.append({"Name":      gettypename(thisfulltype),
                      "FullName":  gettypefullname(gettypenamespace(thisfulltype), gettypename(thisfulltype)),
                      "Namespace": gettypenamespace(thisfulltype), "TypeKind": get_typekind(thisfulltype),
                      "Modifiers": get_type_modifiers(thisfulltype), "BaseTypes": getbasetypes(thisfulltype),
                      "TypeModel": buildtypemodel(thisfulltype)})
    return types

def buildtypemodel(thistype, replacenames=True):
    fieldtypes = [getfieldtype(field, replacenames) for field in getfieldslist(getfullfields(thistype))]
    propertytypes = [{"Type": getpropertytype(_property, replacenames), "Accessors": getpropertyaccessors(_property)}
                     for _property in getpropertieslist(getfullproperties(thistype))]
    methodtypes = [
            {"Type": getmethodtype(method, replacenames), "ParamTypes": getmethodparamtypes(method, replacenames)} for
            method in getmethodslist(getfullmethods(thistype))]
    return {"Fields": fieldtypes, "Properties": propertytypes, "Methods": methodtypes}


def compare_typemodels(unobfuscated, obfuscated, domodifiers=True, dosize=True, dofields=True, domethodparams=True):
    """
    Compares two type models and returns a similarity score from 0 to 100 (0 if they have no similarities or
    if they absolutely cannot match)

    **Make sure first parameter is unobfuscated and second is obfuscated**
    """
    maxscore = float(0)
    score = float(0)
    # Size
    if dosize:
        maxscore += 8
        size1 = (len(unobfuscated.get("Fields")) + len(unobfuscated.get("Methods")) + len(
                unobfuscated.get("Properties")))
        size2 = (len(obfuscated.get("Fields")) + len(obfuscated.get("Methods")) + len(obfuscated.get("Properties")))
        # Depending on the difference in size, this could have a small impact, or be very bad
        # FIXME: This can be in the negatives
        score = 8 - ((abs(size2 - size1) / DeobfuscationWeights.size_benchmark) * DeobfuscationWeights.size_weight)
    # Fields
    if dofields:
        fields1 = list(unobfuscated.get("Fields"))
        fields2 = list(obfuscated.get("Fields"))
        maxscore += len(fields1) * DeobfuscationWeights.field_weight
        # We are using the fields type models, not the fields themselvles
        templist = list(fields2)
        templist2 = list(fields1)
        # it's very normal to add on things, but not as common to delete them. So, most of the fields in the
        # unobfuscated (earlier) one should also exist in the obfuscated one (newer)
        for item in templist2:
            if len(templist) > 0:
                if item in templist:
                    score += DeobfuscationWeights.field_weight
                    templist.remove(item)
    # Methods
    if domethodparams:
        methods1 = list(unobfuscated.get("Methods"))
        methods2 = list(obfuscated.get("Methods"))
    else:
        methods1 = [method["Type"] for method in unobfuscated.get("Methods")]
        methods2 = [method["Type"] for method in unobfuscated.get("Methods")]
    maxscore += len(methods1) * DeobfuscationWeights.method_weight
    templist = list(methods2)
    templist2 = list(methods1)
    # it's very normal to add on things, but not as common to delete them. So, most of the fields in the
    # unobfuscated (earlier) one should also exist in the obfuscated one (newer)
    for item in templist2:
        if len(templist) > 0:
            if item in templist:
                score += DeobfuscationWeights.method_weight
                templist.remove(item)
    # Properties
    properties1 = list(unobfuscated.get("Properties"))
    properties2 = list(obfuscated.get("Properties"))
    maxscore += len(unobfuscated.get("Properties")) * DeobfuscationWeights.property_weight
    templist = list(properties2)
    templist2 = list(properties1)
    # it's very normal to add on things, but not as common to delete them. So, most of the fields in the
    # unobfuscated (earlier) one should also exist in the obfuscated one (newer)
    for item in templist2:
        if len(templist) > 0:
            if item in templist:
                score += DeobfuscationWeights.property_weight
                templist.remove(item)
    if maxscore == 0:
        return 100
    return score / maxscore * 100
