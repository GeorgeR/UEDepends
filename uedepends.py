# Based off https://github.com/nflath/cppdepends

import re, os, sys, tempfile, collections, copy, enum

engine_path = 'V:\UnrealEngine\Engine'
project_path = 'X:\Frontier\client\Game'

name_regex = re.compile(r'(?:public class)\s+(.*)\s?:')
public_module_names_regex = re.compile(r'(?:PublicDependencyModuleNames)(?:(?:.*?))\{(.*?)\}', flags = re.DOTALL)
private_module_names_regex = re.compile(r'(?:PrivateDependencyModuleNames)(?:(?:.*?))\{(.*?)\}', flags = re.DOTALL)
include_regex = re.compile(r'#include *"([^"]*)')
base_class_regex = re.compile(r'(?:public class (?:.*):)(.*)')

class ModuleType(enum.Enum):
    Developer = 0
    Runtime = 1
    Editor = 2

class ModuleInfo(object):
    def _parse_list(self, str_list):
        return [str.strip().replace('"', '').replace(',', '') for str in str_list.split() if str.strip().startswith('\"')] 

    def __init__(self, file_path, file_contents, type):
        self.path = os.path.dirname(file_path)
        self.name = name_regex.search(file_contents).group(1).strip()
        self.type = type

        self.public_dependency_module_names = []
        module_names = public_module_names_regex.search(file_contents)
        if module_names != None:
            self.public_dependency_module_names = self._parse_list(module_names.group(1))

        self.private_dependency_module_names = []
        module_names = None
        module_names = private_module_names_regex.search(file_contents)
        if module_names != None:
            self.private_dependency_module_names = self._parse_list(module_names.group(1))

        self.headers = []
        for root, dirs, files in os.walk(self.path):
            for file in files:
                if file.endswith('.h'):
                    self.headers.append(file)

    def get_referenced_modules(self):
        return self.public_dependency_module_names + self.private_dependency_module_names

    # Find actual dependencies (from includes) and return a list of redundant public and private modules
    def discover_dependencies(self, other_modules = None):
        redundant_module_references = self.public_dependency_module_names + self.private_dependency_module_names
        for root, dirs, files in os.walk(self.path):
            for file in files:
                if file.endswith('.cpp') or file.endswith('.h'):
                    file_path = os.path.abspath(os.path.join(root, file))
                    with open(file_path, 'r') as file:
                        file_contents = file.read(-1)
                        for match in include_regex.finditer(file_contents):
                            match = match.group(1).split('/')[-1]
                            if match not in self.headers:
                                for module_reference_name in redundant_module_references:
                                    if module_reference_name in other_modules:
                                        module = other_modules[module_reference_name]
                                        if module.has_header(match):
                                            for referenced_module in module.get_referenced_modules():
                                                if referenced_module in redundant_module_references:
                                                    redundant_module_references.remove(referenced_module)
                                            redundant_module_references.remove(module_reference_name)

        return redundant_module_references

    def has_header(self, header_name):
        return header_name in self.headers

    @staticmethod
    def parse(build_file_path, type):
        if os.path.isfile(build_file_path):
            with open(build_file_path, 'r') as file:
                file_contents = file.read(-1)

                is_build_file = base_class_regex.search(file_contents)
                if is_build_file == None:
                    return None
                
                is_build_file = is_build_file.group(1).strip() == 'ModuleRules'
                if is_build_file == False:
                    return None

                return ModuleInfo(build_file_path, file_contents, type)

def discover_modules(root):
    result = []
    for root, dirs, files in os.walk(root):
        for file in files:
            if file.endswith('.cs'):
                file_path = os.path.abspath(os.path.join(root, file))
                module_info = ModuleInfo.parse(file_path, ModuleType.Developer)
                if module_info is not None:
                    result.append(module_info)

    return result

print('Discovering Engine Modules...')
engine_module_infos = discover_modules(engine_path)

print('Discovering Project Modules...')
project_module_infos = discover_modules(project_path)

all_module_infos = engine_module_infos + project_module_infos
all_module_infos = dict((info.name, info) for info in all_module_infos)
core = all_module_infos['Core']

print('Discovering Dependencies...')
for m in project_module_infos:
    redundant_dependencies = m.discover_dependencies(all_module_infos)
    if len(redundant_dependencies) > 0:
        print("Module: %s has the following redundant dependencies: %s" % (m.name, redundant_dependencies))