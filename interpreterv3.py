from classv2 import ClassDef, TemplateClassDef
from intbase import InterpreterBase, ErrorType
from bparser import BParser
from objectv2 import ObjectDef
from type_valuev2 import TypeManager
from pathlib import Path
from argparse import ArgumentParser, ArgumentTypeError

# need to document that each class has at least one method guaranteed

# Main interpreter class
class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output

    # run a program, provided in an array of strings, one string per line of source code
    # usese the provided BParser class found in parser.py to parse the program into lists
    def run(self, program):
        status, parsed_program = BParser.parse(program)
        if not status:
            super().error(
                ErrorType.SYNTAX_ERROR, f"Parse error on program: {parsed_program}"
            )
        self.__add_all_class_types_to_type_manager(parsed_program)
        self.__map_class_names_to_class_defs(parsed_program)

        # instantiate main class
        invalid_line_num_of_caller = None
        self.main_object = self.instantiate(
            InterpreterBase.MAIN_CLASS_DEF, invalid_line_num_of_caller
        )

        # call main function in main class; return value is ignored from main
        self.main_object.call_method(
            InterpreterBase.MAIN_FUNC_DEF, [], False, invalid_line_num_of_caller
        )

        # program terminates!

    # user passes in the line number of the statement that performed the new command so we can generate an error
    # if the user tries to new an class name that does not exist. This will report the line number of the statement
    # with the new command
    def instantiate(self, class_name, line_num_of_statement):
        if class_name not in self.class_index:
            super().error(
                ErrorType.TYPE_ERROR,
                f"No class named {class_name} found",
                line_num_of_statement,
            )
        class_def = self.class_index[class_name]
        obj = ObjectDef(
            self, class_def, None, self.trace_output
        )  # Create an object based on this class definition
        return obj

    # returns a ClassDef object
    def get_class_def(self, class_name, line_number_of_statement):
        if class_name not in self.class_index:
            super().error(
                ErrorType.TYPE_ERROR,
                f"No class named {class_name} found",
                line_number_of_statement,
            )
        return self.class_index[class_name]

    # returns a bool
    def is_valid_type(self, typename):
        return self.type_manager.is_valid_type(typename)

    # returns a bool
    def is_a_subtype(self, suspected_supertype, suspected_subtype):
        return self.type_manager.is_a_subtype(suspected_supertype, suspected_subtype)

    # typea and typeb are Type objects; returns true if the two type are compatible
    # for assignments typea is the type of the left-hand-side variable, and typeb is the type of the
    # right-hand-side variable, e.g., (set person_obj_ref (new teacher))
    def check_type_compatibility(self, typea, typeb, for_assignment=False):
        return self.type_manager.check_type_compatibility(typea, typeb, for_assignment)
    
    def check_template(self, class_name):
        split_name = class_name.split('@')

        if split_name[0] not in self.template_class_index or len(split_name) == 1:
            return False
        for typ in split_name[1:]:
            if not self.type_manager.is_valid_type(typ):
                return False

        self.type_manager.add_class_type(class_name, None)
        self.add_parameterized_template(class_name, split_name)
        return True
    
    def add_parameterized_template(self, class_name, split_name):
        template_def = self.template_class_index[split_name[0]]
        template_source = template_def.class_source
        object_name = template_def.object_name
        template_params = template_source[2]
        actual_types = split_name[1:]
        for i in range(len(template_params)):
            self.replace_template_with_types(template_source, template_params[i], actual_types[i])
        self.replace_template_with_types(template_source, object_name, class_name)
        self.class_index[class_name] = ClassDef(template_source, self)

    def replace_template_with_types(self, template_source, template_param, actual_type):
        for i in range(len(template_source)):
            item = template_source[i]
            if isinstance(item, list):
                self.replace_template_with_types(item, template_param, actual_type)
            elif item == template_param:
                if i == 0 or i == 1:
                    template_source[i] = actual_type

    def __map_class_names_to_class_defs(self, program):
        self.class_index = {}
        self.template_class_index = {}
        for item in program:
            if item[0] == InterpreterBase.CLASS_DEF:
                if item[1] in self.class_index or item[1] in self.template_class_index:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        f"Duplicate class name {item[1]}",
                        item[0].line_num,
                    )
                self.class_index[item[1]] = ClassDef(item, self)
            
            if item[0] == InterpreterBase.TEMPLATE_CLASS_DEF:
                if item[1] in self.template_class_index or item[1] in self.class_index:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        f"Duplicate class name {item[1]}",
                        item[0].line_num,
                    )
                self.template_class_index[item[1]] = TemplateClassDef(item, self, item[2])

    # [class classname inherits superclassname [items]]
    def __add_all_class_types_to_type_manager(self, parsed_program):
        self.type_manager = TypeManager()
        for item in parsed_program:
            if item[0] == InterpreterBase.CLASS_DEF:
                class_name = item[1]
                superclass_name = None
                if item[2] == InterpreterBase.INHERITS_DEF:
                    superclass_name = item[3]
                self.type_manager.add_class_type(class_name, superclass_name)
            
            if item[0] == InterpreterBase.TEMPLATE_CLASS_DEF:
                class_name = item[1]
                self.type_manager.add_class_type(class_name, None)


def main() -> None:
    """Test code for invoking directly from the command line.

    USAGE: python3 interpreterv1.py [-v | --verbose] SOURCE
    """
    def valid_path(value: str) -> Path:
        path = Path(value)
        if path.is_file():
            return path
        # Attempt to infer .brewin extension
        if not path.suffix:
            path = path.with_suffix(".brewin")
            if path.is_file():
                return path
        raise ArgumentTypeError(f"{value!r} is not a valid file.")

    parser = ArgumentParser(description="Interpret a Brewin source file.")
    parser.add_argument("source_path", metavar="SOURCE", type=valid_path,
                        help="text file to interpret")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="run interpreter with trace_output=True")

    namespace = parser.parse_args()
    source_path: Path = namespace.source_path
    verbose: bool = namespace.verbose

    with source_path.open("rt", encoding="utf-8") as source:
        source_lines = source.read().splitlines()

    interpreter = Interpreter(trace_output=verbose)
    interpreter.run(source_lines)


if __name__ == "__main__":
    main()
