#! /usr/bin/python3

import os
import sys
import xml.etree.ElementTree as ElementTree

DO_TANGLE = True
if sys.argv[1] == '--no-binary':
	DO_TANGLE = False
	sys.argv.pop(1)

root = ElementTree.parse(sys.argv[1]).getroot()
if root.tag != 'web':
	print(f"Expected: <web>, received <{root.tag}> as root node", file = sys.stderr)
	exit(1)

SNIPPETS = {}

def collect_snippets(node):
	global SNIPPETS
	if node.tag == 'code' and 'id' in node.attrib:
		snippet_id = node.attrib['id']
		if snippet_id in SNIPPETS:
			print(f"Warning: duplicate code ID {snippet_id}", file = sys.stderr)
		else:
			SNIPPETS[snippet_id] = node
	for child in node:
		collect_snippets(child)

collect_snippets(root)

WEAVE = 'weave'
TANGLE = 'tangle'

def process_code(node, method, file):
	global WEAVE, TANGLE
	if method == WEAVE:
		if node.text is not None:
			print(node.text.replace('&', '&amp').replace('<', '&lt;'), end = '', file = file)
		for child in node:
			text = "<" + child.tag
			for attrib in child.attrib.items():
				text += " " + attrib[0] + "=\"" + attrib[1].replace('&', '&amp;').replace('"', '&quot;') + "\""
			text += ">"
			print(text, end = '', file = file)
			process_code(child, method, file)
			text = "</" + child.tag + ">"
			if child.tail is not None:
				text += child.tail
			print(text, end = '', file = file)
	elif method == TANGLE:
		if node.text is not None:
			print(node.text, end = '', file = file)
		for child in node:
			process_code(child, method, file)
			if child.tail is not None:
				print(child.tail, end = '', file = file)

GENERATED_C_FILES = []
GENERATED_FILES = set()
def process_node(node, method, file, version = None):
	global WEAVE, TANGLE, SNIPPETS, GENERATED_C_FILES
	if node.tag == WEAVE:
		filename = node.attrib['filename']
		GENERATED_FILES.add(filename)
		file = open(os.path.join(sys.argv[2], filename), 'w')
		print("<!doctype html>", file = file)
		print("<html>", file = file)
		for child in node:
			process_node(child, WEAVE, file, None)
		print("</html>", file = file)
		file.close()
	elif node.tag == TANGLE:
		if not DO_TANGLE:
			return

		for version in ['xlib', 'xcb']:
			filename = node.attrib['filename'].replace('%', version)
			if filename in GENERATED_C_FILES:
				print(f"Error: overwriting already generated file {filename}", file = sys.stderr)
			GENERATED_FILES.add(filename)
			GENERATED_C_FILES.append(filename)
			file = open(os.path.join(sys.argv[2], filename), 'w')
			if node.text is not None:
				print(node.text.strip(), file = file)
			for child in node:
				process_node(child, TANGLE, file, version)
			file.close()
	elif method == WEAVE:
		if node.tag == 'code' or node.tag == 'include':
			print("""<table border='1' width='100%'>
<tr>
<td width="50%">Xlib</td>
<td width="50%">XCB</td>
</tr>
<tr>""", file = file)
			versions = {}
			code_id = node.attrib.get('id')
			if node.tag == 'code':
				source_node = node
			elif node.tag == 'include':
				if code_id not in SNIPPETS:
					print(f"Error: undefined snippet {code_id}", file = sys.stderr)
					exit(1)
				source_node = SNIPPETS[code_id]
			for snippet_version in source_node:
				if snippet_version.tag == 'version':
					version_name = snippet_version.attrib['name']
					if version in versions:
						print(f"Error: repeated version name {version_name} for code snippet {code_id}", file = sys.stderr)
					else:
						if version_name not in {'xlib', 'xcb'}:
							print(f"Warning: unrecognized version name {version_name} for code snippet {code_id}", file = sys.stderr)
					versions[version_name] = snippet_version
			for version in ['xlib', 'xcb']:
				if version not in versions:
					print("<td></td>", file = file)
				else:
					print("<td><pre>", end = '', file = file)
					process_code(versions[version], WEAVE, file)
					print("</pre></td>", file = file)
			print("""</tr>
</table>""", file = file)
		else:
			text = "<" + node.tag
			for attrib in node.attrib.items():
				text += " " + attrib[0] + "=\"" + attrib[1].replace('&', '&amp;').replace('"', '&quot;') + "\""
			text += ">"
			if node.text is not None:
				text += node.text.replace('&', '&amp;').replace('<', '&lt;')
			print(text, end = '', file = file)
			for child in node:
				process_node(child, method, file, version)
			text = "</" + node.tag + ">"
			if node.tail is not None:
				text += node.tail
			print(text, end = '', file = file)
	elif method == TANGLE:
		if node.tag == 'include':
			ignore = False
			included = False
			if 'version' in node.attrib and node.attrib['version'] != version:
				ignore = True
			if 'id' not in node.attrib:
				print(f"Error: missing attribute 'id' for <include>", file = sys.stderr)
				ignore = True
			else:
				snippet_id = node.attrib['id']
				if snippet_id not in SNIPPETS:
					print(f"Error: undefined snippet {snippet_id}", file = sys.stderr)
					ignore = True
			if not ignore:
				snippet = SNIPPETS[snippet_id]
				for snippet_version in snippet:
					if snippet_version.tag == 'version' and snippet_version.attrib['name'] == version:
						print(f"/* snippet '{snippet_id}' */", file = file)
						process_code(snippet_version, TANGLE, file)
						included = True
			if node.tail is not None:
				if included:
					print(f"/* end of snippet */", file = file)
				print(node.tail.strip(), file = file)
		else:
			print(f"Error: unrecognized tag in <tangle>: <{node.tag}>", file = sys.stderr)

for child in root:
	process_node(child, None, None, None)

if not DO_TANGLE:
	exit()

GENERATED_FILES.add('Makefile')
with open(os.path.join(sys.argv[2], 'Makefile'), 'w') as file:
	for filename in GENERATED_C_FILES:
		GENERATED_FILES.add(os.path.splitext(filename)[0])
	print("all: " + " ".join(os.path.splitext(filename)[0] for filename in GENERATED_C_FILES), file = file)
	print(file = file)
	print("%-xlib: %-xlib.c", file = file)
	print("\tgcc -o $@ $< -lX11", file = file)
	print(file = file)
	print("%-xcb: %-xcb.c", file = file)
	print("\tgcc -o $@ $< -lxcb", file = file)
	print(file = file)
	print(".PHONY: all clean", file = file)
	print(file = file)

	# if separate 32-bit and 64-bit versions are needed
	for filename in GENERATED_C_FILES:
		GENERATED_FILES.add(os.path.splitext(filename)[0] + ".32")
		GENERATED_FILES.add(os.path.splitext(filename)[0] + ".64")
	print("allbits: " + " ".join(os.path.splitext(filename)[0] + ".32 " + os.path.splitext(filename)[0] + ".64" for filename in GENERATED_C_FILES), file = file)
	print(file = file)
	for bits in [32, 64]:
		print(f"%-xlib.{bits}: %-xlib.c", file = file)
		print(f"\tgcc -m{bits} -o $@ $< -lX11", file = file)
		print(file = file)
		print(f"%-xcb.{bits}: %-xcb.c", file = file)
		print(f"\tgcc -m{bits} -o $@ $< -lxcb", file = file)
		print(file = file)

	print("clean:", file = file)
	print("\trm -f " + " ".join(GENERATED_FILES), file = file)
	print(file = file)

