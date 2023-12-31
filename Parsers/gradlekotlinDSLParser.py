import glob
import os
import re


def gradlekotlinDSLParser(path, sbom):
    paths = glob.glob(os.path.join(path, "**", "build.gradle.kts"), recursive=True)

    for p in paths:
        dependencies = {}
        with open(p, "r") as file:
            content = file.read()

            name = os.path.split(os.path.dirname(p))[-1]

            group_match = re.search(r"group = \"(.*)\"", content)
            grp = group_match.group(1) if group_match else ""

            version_match = re.search(r"version = \"(.*)\"", content)
            ver = version_match.group(1) if version_match else ""

            source_match = re.search(r"sourceCompatibility = (.*)", content)
            src = source_match.group(1) if source_match else ""

            purl = f"pkg:maven/{grp}/{name}@{ver}"
            bomref = purl
            if "components" not in sbom["metadata"]["component"]:
                sbom["metadata"]["component"]["components"] = []
            sbom["metadata"]["component"]["components"].append(
                {
                    "group": grp,
                    "name": name,
                    "version": ver,
                    "purl": purl,
                    "type": "library",
                    "bom-ref": bomref,
                    "properties": [
                        {"name": "buildFile", "value": p},
                        {"name": "projectDir", "value": os.path.split(p)[0]},
                        {"name": "rootDir", "value": path},
                    ],
                }
            )
        with open(p, "r") as file:
            inside_dependencies = False
            varname={}
            for line in file:
                line = line.strip()
                if line == "dependencies {":
                    inside_dependencies = True
                    continue
                elif line == "}":
                    if inside_dependencies:
                        break
                elif inside_dependencies:
                    match = re.match(r"val (.+) = \"(.+)\"", line)
                    if match:

                        key=match.group(1)
                        varname[key]=match.group(2)
                    match = re.match(r"(\w+)\(\"(.+):(.+):(.+)\"\)", line)
                    if match:
                        scope, group, name, version = match.groups()
                        if version[1:] in varname.keys():
                            version = varname[version[1:]]

                        purl = f"pkg:maven/{group}/{name}@{version}"
                        bomref = purl
                        component = {
                            "group": group,
                            "name": name,
                            "version": version,
                            "purl": purl,
                            "type": "library",
                            "bom-ref": bomref,
                            "evidence": {
                                "identity": {
                                    "field": "purl",
                                    "confidence": 1,
                                    "methods": [
                                        {
                                            "technique": "manifest-analysis",
                                            "confidence": 1,
                                            "value": p,
                                        }
                                    ],
                                }
                            },
                            "properties": [{"name": "GradleProfileName", "value": p}],
                        }

                        # value = (
                        #     "api"
                        #     if scope in ["implementation", "api", "kapt"]
                        #     else "testCompileClasspath"
                        #     if scope
                        #     in [
                        #         "testImplementation",
                        #         "testCompileOnly",
                        #         "testRuntimeOnly",
                        #     ]
                        #     else "runtimeClasspath"
                        #     if scope in ["runtimeOnly"]
                        #     else "compileOnlyClasspath"
                        #     if scope in ["compileOnly"]
                        #     else "unknown"
                        # )
                        scope = (
                            "required"
                            if scope in ["implementation", "api"]
                            else "optional"
                            if scope
                            in [
                                "compileOnly",
                                "runtimeOnly",
                                "testImplementation",
                                "testCompileOnly",
                                "testRuntimeOnly",
                            ]
                            else scope
                        )
                        if scope != "classpath":
                            component["scope"] = scope
                        #     component["properties"] = [
                        #         {"name": "GradleProfileName", "value": value}
                        #     ]

                        sbom["components"].append(component)
                    dependencies[bomref] = []

        for ref, dep in dependencies.items():
            sbom["dependencies"].append({"ref": ref, "dependsOn": dep})
