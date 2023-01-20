#!/usr/bin/env python3

import pyparsing as pp


class FileParser:
    """Abstraction of OpenFOAMs config files which contain key value pairs or key block pairs"""

    def __init__(self, **kwargs):
        pass

    # TODO move to separate file for the grammar
    @property
    def dimensionSet(self):
        """Parse OF dimension set eg  [0 2 -1 0 0 0 0]"""
        return (
            pp.Suppress("[")
            + pp.delimitedList(pp.pyparsing_common.number * 7, delim=pp.White())
            + pp.Suppress("]")
        ).setParseAction(lambda toks: "[" + " ".join([str(i) for i in toks]) + "]")

    @property
    def footer(self):
        """the footer of a OpenFOAM file"""
        return "//" + "*" * 73 + "//\n"

    @property
    def separator(self):
        return "// " + "* " * 26 + "//"

    @property
    def of_list(self):
        """matches (a b c)"""
        return (
            pp.Suppress("(")
            + pp.delimitedList(
                pp.OneOrMore(self.extended_alphanum), delim=" "
            ).add_parse_action(lambda t: [_ for _ in t])
            + pp.Suppress(")")
        ).set_results_name("of_list")

    @property
    def key_value_pair(self):
        """matches a b; or a (a b c); or a {foo bar;}"""
        of_dict = pp.Forward()
        key_val_pair = (
            pp.Group(
                pp.Word(pp.alphanums + '"#(),|*').set_results_name("key")
                + (
                    of_dict
                    ^ pp.OneOrMore(
                        pp.Word(pp.alphanums + '".-') + pp.Suppress(";")
                    )  # all kinds of values delimeted by ;
                    ^ pp.Word(
                        pp.alphanums + '".-/'
                    )  # for includes which are single strings can contain /
                    ^ self.of_list + pp.Suppress(";")
                ).set_results_name("value")
                # a variable
                ^ pp.Literal("$") + pp.Word(pp.alphanums) + pp.Suppress(";")
            )
            .ignore(pp.cStyleComment | pp.dblSlashComment)
            .set_results_name("key_value_pair")
        )
        of_dict <<= (
            pp.Suppress("{") + pp.ZeroOrMore(key_val_pair) + pp.Suppress("}")
        ).set_results_name("of_dict")
        return key_val_pair

    @property
    def extended_alphanum(self):
        # TODO rename
        return pp.Word(pp.alphanums + '#_-."/')

    @property
    def single_line_comment(self):
        """matches a b; or a (a b c);"""
        return pp.Group(
            pp.Literal("//") + pp.ZeroOrMore(pp.Word(pp.alphanums + '#_-."/'))
        ).set_results_name("single_line_comment")

    @property
    def config_parser(self):
        return pp.Group(
            pp.ZeroOrMore(self.single_line_comment) ^ pp.ZeroOrMore(self.key_value_pair)
        )

    def key_value_to_dict(self, parse_result):
        """converts a ParseResult of a list of  key_value_pair to a python dict"""
        ret = {}
        for res in parse_result:
            # probe if next result is str or ParseResult
            if isinstance(res, pp.results.ParseResults):
                if res.get_name() == "key_value_pair":
                    key = res.key
                    # keys starting with # need special attention to avoid overwriting
                    # them in the return dictionary
                    if key.startswith("#"):
                        key = res[0] + "_" + res[1]
                    if key.startswith("$"):
                        key = res[0] + "_" + res[1]

                    # TODO use of_dict over kvp if it works
                    # if res.get("of_dict"):
                    #     ret.update({key: self.key_value_to_dict(res.get("of_dict"))})
                    if res.get("key_value_pair"):
                        d = {key: self.key_value_to_dict([v for v in res.value])}
                        ret.update(d)
                    elif res.get("of_list"):
                        ret.update({key: res.get("of_list").as_list()})
                    elif res.get("value"):
                        ret.update({key: res.get("value")[0]})
            else:
                print(res, type(res))
                return res
        return ret

    def parse_file_to_dict(self):
        """parse an OpenFOAM file to an Ordered dict"""
        list_text = self.read(self.path)
        self.of_comment_header = list_text[0:7]
        self.of_header = list_text[7:15]
        self.text = "\n".join(list_text[15:])
        self.parse = self.config_parser.search_string(self.text)
        # if len(self.parse) is bigger than one the parse function
        # did not consume the file entirely and something went most likely wrong
        self._dict = self.key_value_to_dict(self.parse[0][0])
        return self._dict

    def read(self, fn):
        """parse an OF file into a dictionary"""
        with open(fn, "r") as fh:
            return fh.readlines()

    def write_to_disk(self):
        """writes a parsed OF file back into a file"""
        fn = self.path
        dictionary = self._dict

        def to_str_kvp(item, indent="", nl="\n\n"):
            key, value = item
            print(key, value)
            if key.startswith("#"):
                return "{}{} {}{}".format(indent, key.split("_")[0], value, nl)
            if key == "functions":
                ret = "functions {\n"
                for k, v in value.items():
                    ret += to_str_kvp((k, v), indent + "\t", nl="\n")
                ret += "}\n\n"
                return ret
            if isinstance(value, str):
                return indent + "{}\t{};{}".format(key, value, nl)
            if isinstance(value, dict):
                s = "{}{}\n{}{{\n".format(indent, key, indent)
                new_indent = indent + "\t"
                for k, v in value.items():
                    s += to_str_kvp((k, v), new_indent, nl="\n")
                s += indent + "}\n\n"
                return s
            elif isinstance(value, list):
                joined_values = " ".join(value)
                return indent + "{} ({});".format(key, joined_values)
            return ""

        with open(fn, "w") as fh:
            for line in self.of_comment_header:
                fh.write(line)
            for line in self.of_header:
                fh.write(line)
            fh.write("\n")
            for key, value in dictionary.items():
                fh.write(to_str_kvp((key, value)))
            fh.write(self.footer)

    def set_key_value_pairs(self, dictionary):
        """check if a given key exists and replaces it with the key value pair

        this can be used to modify the value in the file
        """
        sub_dict = dictionary.get("set")
        if sub_dict:
            dictionary.pop("set")
            d = self._dict
            for s in sub_dict.split("/"):
                d = d[s]
        else:
            d = self._dict
        d.update(dictionary)
        self.write_to_disk()
