"""Copyright 2019 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from __future__ import print_function

import argparse
import os.path
from election_results_xml_validator import base
from election_results_xml_validator import rules
from election_results_xml_validator import version

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


def _validate_file(parser, arg):
  """Check that the files provided exist."""
  if not os.path.exists(arg):
    parser.error("The file %s doesn't exist" % arg)
  else:
    return arg


def _validate_rules(parser, arg):
  """Check that the listed rules exist"""
  invalid_rules = []
  rule_names = [x.__name__ for x in rules.RULES]
  input_rules = arg.strip().split(",")
  for rule in input_rules:
    if rule and rule not in rule_names:
      invalid_rules.append(rule)
  if invalid_rules:
    parser.error("The rule(s) %s do not exist" % ", ".join(invalid_rules))
  else:
    return input_rules


def _validate_severity(parser, arg):
  """Check that the severity level provided is correct."""

  _VALID_SEVERITIES = {"info": 0, "warning": 1, "error": 2}
  if arg.strip().lower() not in _VALID_SEVERITIES:
    parser.error("Invalid severity. Options are error, warning, or info")
  else:
    return _VALID_SEVERITIES[arg.strip().lower()]


def _validate_country_codes(parser, arg):
  """Check that the supplied 2 country code is correct.

    The repo is at https://github.com/opencivicdata/ocd-division-ids
    """
  country_codes = [
      "au", "ca", "cl", "de", "fi", "in", "nz", "mx", "ua", "us", "br"
  ]
  if arg.strip().lower() not in country_codes:
    parser.error("Invalid country code. Available codes are: %s" %
                 ", ".join(country_codes))
  else:
    return arg.strip().lower()


def arg_parser():
  """Parser for command line arguments."""

  description = ("Script to validate that an elections results XML file "
                 "follows best practices")
  parser = argparse.ArgumentParser(description=description)
  subparsers = parser.add_subparsers(dest="cmd")
  parser_validate = subparsers.add_parser("validate")
  parser_validate.add_argument(
      "-x",
      "--xsd",
      help="Common Data Format XSD file path",
      required=True,
      metavar="xsd_file",
      type=lambda x: _validate_file(parser, x))
  parser_validate.add_argument(
      "election_file",
      help="XML election file to be validated",
      metavar="election_file",
      type=lambda x: _validate_file(parser, x))
  parser_validate.add_argument(
      "--ocdid_file",
      help="Local ocd-id csv file path",
      required=False,
      metavar="csv_file",
      type=lambda x: _validate_file(parser, x))
  group = parser_validate.add_mutually_exclusive_group(required=False)
  group.add_argument(
      "-i",
      help="Comma separated list of rules to be validated.",
      required=False,
      type=lambda x: _validate_rules(parser, x))
  group.add_argument(
      "-e",
      help="Comma separated list of rules to be excluded.",
      required=False,
      type=lambda x: _validate_rules(parser, x))
  parser_validate.add_argument(
      "--verbose",
      "-v",
      action="store_true",
      help="Print out detailed log messages. Defaults to False",
      required=False)
  parser_validate.add_argument(
      "--severity",
      "-s",
      type=lambda x: _validate_severity(parser, x),
      help="Minimum issue severity level - error, warning or info",
      required=False)
  parser_validate.add_argument(
      "-g",
      help="Skip check to see if there is a new OCD ID file on Github."
      "Defaults to True",
      action="store_true",
      required=False)
  parser_validate.add_argument(
      "-c",
      help="Two letter country code for OCD IDs.",
      metavar="country",
      type=lambda x: _validate_country_codes(parser, x),
      required=False,
      default="us")
  subparsers.add_parser("list")
  return parser


def print_metadata(filename):
  """Prints metadata associated with this run of the validator."""
  print("Validator version: {}".format(version.__version__))

  blocksize = 65536
  digest = hashes.Hash(hashes.SHA512_256(), backend=default_backend())
  with open(filename, "rb") as f:
    for block in iter(lambda: f.read(blocksize), b""):
      digest.update(block)
  print("SHA-512/256 checksum: {}".format(digest.finalize().hex()))


def main():
  p = arg_parser()
  options = p.parse_args()
  if options.cmd == "list":
    print("Available rules are :")
    for rule in rules.RULES:
      print("\t" + rule.__name__ + " - " + rule.__doc__.split("\n")[0])
    return
  elif options.cmd == "validate":
    rules_to_check = []
    if options.i:
      rules_to_check = options.i
    elif options.e:
      rules_to_check = [
          x.__name__ for x in rules.RULES if x.__name__ not in options.e
      ]
    else:
      rules_to_check = [x.__name__ for x in rules.RULES]
    rule_options = {}
    if options.g:
      rule_options.setdefault("ElectoralDistrictOcdId", []).append(
          base.RuleOption("check_github", False))
      rule_options.setdefault("GpUnitOcdId", []).append(
          base.RuleOption("check_github", False))
    if options.c:
      rule_options.setdefault("ElectoralDistrictOcdId", []).append(
          base.RuleOption("country_code", options.c))
      rule_options.setdefault("GpUnitOcdId", []).append(
          base.RuleOption("country_code", options.c))
    if options.ocdid_file:
      rule_options.setdefault("ElectoralDistrictOcdId", []).append(
          base.RuleOption("local_file", options.ocdid_file))
      rule_options.setdefault("GpUnitOcdId", []).append(
          base.RuleOption("local_file", options.ocdid_file))
    rule_classes_to_check = [
        x for x in rules.RULES if x.__name__ in rules_to_check
    ]

    print_metadata(options.election_file)

    registry = base.RulesRegistry(
        election_file=options.election_file,
        schema_file=options.xsd,
        rule_classes_to_check=rule_classes_to_check,
        rule_options=rule_options)
    found_errors = registry.check_rules()
    registry.print_exceptions(options.severity, options.verbose)
    # TODO other error codes?
    return found_errors


if __name__ == "__main__":
  main()
