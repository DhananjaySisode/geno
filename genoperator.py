import datetime;
import subprocess;


def helmoperator(helmrepo, helmchart, operatorname):
    result = subprocess.run(["helm", "repo", "add", "bitnami", helmrepo], stdout=subprocess.PIPE)
    print("output %s" % result)
    operatorDirectory = "/root/operators/" + operatorname

    result = subprocess.run(["mkdir", operatorDirectory], stdout=subprocess.PIPE)
    print("output %s" % result)
    result = subprocess.run(["operator-sdk", "init", "--plugins=helm", "--helm-chart", helmchart],
                            cwd=operatorDirectory, stdout=subprocess.PIPE)
    print("output %s" % result)
    ct = datetime.datetime.now()
    date_time = ct.strftime("%m/%d/%Y %H:%M:%S")
    with open('database/operators.csv', 'a') as f:
        f.write(operatorname + ",helm," + date_time + "," + operatorDirectory + "\n")
    return


def ansibleoperatorfromk8s(groupname, domainname, operatorname, version, kinds, namespace):
    operatorDirectory = "/root/operators/" + operatorname

    result = subprocess.run(["mkdir", operatorDirectory], stdout=subprocess.PIPE)
    print("output %s" % result)
    result = subprocess.run(["operator-sdk", "init", "--plugins=ansible", "--domain", domainname],
                            cwd=operatorDirectory, stdout=subprocess.PIPE)
    print("output %s" % result)
    # print(kinds)
    # Create each kind given in "kinds" list
    for kind in kinds:
        # print(kind)
        result = subprocess.run(["operator-sdk", "create", "api", "--group", groupname, "--version", version, "--kind",
                                 kind['name'].capitalize(), "--generate-role"], cwd=operatorDirectory,
                                stdout=subprocess.PIPE)
        print("output %s" % result)

        for resource in kind['resourcenames']:
            print("Creating code for " + resource)
            result = subprocess.run(["sh", "createAnsibleCode.sh", resource, kind['name'].lower(), operatorDirectory],
                                    stdout=subprocess.PIPE)
            print("Resource created %s" % result)

    ct = datetime.datetime.now()
    date_time = ct.strftime("%m/%d/%Y %H:%M:%S")
    with open('database/operators.csv', 'a') as f:
        f.write(operatorname + ",from kubernetes," + date_time + "," + operatorDirectory + "\n")
    return


def ansibleoperatorfromscratch(groupname, domainname, operatorname, version, kinds):
    operatorDirectory = "/root/operators/" + operatorname

    result = subprocess.run(["mkdir", operatorDirectory], stdout=subprocess.PIPE)
    print("output %s" % result)
    result = subprocess.run(["operator-sdk", "init", "--plugins=ansible", "--domain", domainname],
                            cwd=operatorDirectory, stdout=subprocess.PIPE)
    print("output %s" % result)

    # Create each kind given in "kinds" list
    for kind in kinds:
        print(kind)
        result = subprocess.run(["operator-sdk", "create", "api", "--group", groupname, "--version", version, "--kind",
                                 kind['name'].capitalize(), "--generate-role"], cwd=operatorDirectory,
                                stdout=subprocess.PIPE)
        print("output %s" % result)

        path = operatorDirectory + "/roles/" + kind['name'].lower() + "/tasks/main.yml"
        for resource in kind['resourcenames']:
            resourcetype = resource["type"]
            if "Deployment" == resourcetype:
                deployment(resource, path)
            elif "Service" == resourcetype:
                service(resource, path, operatorDirectory)
            elif "Route" == resourcetype:
                route(resource, path, operatorDirectory)

    ct = datetime.datetime.now()
    date_time = ct.strftime("%m/%d/%Y %H:%M:%S")
    with open('database/operators.csv', 'a') as f:
        f.write(operatorname + ",from scratch," + date_time + "," + operatorDirectory + "\n")
    return


def deployment(deploymentresource, path):
    with open('./k8s_templates/deployment_template.yaml') as file:
        document = yaml.safe_load(file)
    for item in document:
        # print(item)
        labelslist = [x.strip() for x in deploymentresource["label"].split(':')]
        container = {"name": deploymentresource["name"], "image": deploymentresource["image"],
                     "ports": [{"containerPort": deploymentresource["port"]}]}
        item["k8s"]["definition"]["metadata"]["name"] = deploymentresource["name"]
        item["k8s"]["definition"]["spec"]["replicas"] = deploymentresource["replicas"]
        item["k8s"]["definition"]["spec"]["selector"]["matchLabels"][labelslist[0]] = labelslist[1]
        item["k8s"]["definition"]["spec"]["template"]["metadata"]["labels"][labelslist[0]] = labelslist[1]
        item["k8s"]["definition"]["spec"]["template"]["spec"]["containers"].append(container)

    with open(path, 'a') as f:
        yaml.dump(document, f)
    return 0


def service(serviceresource, path, operatorDirectory):
    with open('./k8s_templates/service_template.yaml') as file:
        document = yaml.safe_load(file)
    for item in document:
        appselector = [x.strip() for x in serviceresource["podselectorlabel"].split(':')]
        item["k8s"]["definition"]["metadata"]["name"] = serviceresource["name"]
        item["k8s"]["definition"]["spec"]["selector"][appselector[0]] = appselector[1]
        item["k8s"]["definition"]["spec"]["ports"]["port"] = serviceresource["sourceport"]
        item["k8s"]["definition"]["spec"]["ports"]["targetPort"] = serviceresource["targetport"]

    with open(path, 'a') as f:
        yaml.dump(document, f)
    return 0


def route(routeresource, path, operatorDirectory):
    ##Add the ansible code in roles/
    with open('./k8s_templates/route_template.yaml') as file:
        document = yaml.safe_load(file)

    for item in document:
        item["k8s"]["definition"]["metadata"]["name"] = routeresource["name"]
        item["k8s"]["definition"]["spec"]["to"]["name"] = routeresource["servicename"]
        item["k8s"]["definition"]["spec"]["port"]["targetPort"] = routeresource["targetport"]

    with open(path, 'a') as f:
        yaml.dump(document, f)
        
    ## Add the rbac permissions in config/rbac/
    with open(operatorDirectory+'/config/rbac/role.yaml') as fileroles:
        documentroles = yaml.safe_load(fileroles)
    
    found=False
    ##Check if permission already there 
    for roles in documentroles["rules"]:
        for resourcelist in roles["resources"]:
           if resourcelist == "routes":
               found=True
               print("Found routes in config/rbac/roles.yaml")
               break
               
    if found==False:
        with open('./rbac_templates/route_rbac.yaml') as filetemplate:
            documenttemplate = yaml.safe_load(filetemplate)
        documentroles["rules"].append(documenttemplate)
        with open(path, 'w') as fileroleswrite:
        yaml.dump(documentroles, fileroleswrite)
        
    return 0

