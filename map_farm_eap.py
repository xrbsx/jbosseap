#!/usr/bin/jython
# encoding: utf-8

## Criado por Rafael Barbosa
## License GPL 2.0

# Este programa conecta ao EAP via CLI, lista as aplicacoes implantadas e apresenta os grupos relacionados.
# Este programa conecta ao EAP via CLI e mapeia seus HOSTS, GROUPS, INTANCES
# Utilizando o comando "deploy" o EAP lista dos as implantacoes hospedadas naquela farm.
# Iterando em cada aplicacao implantada utilizo o comando "deployment-info" para listar os grupos em que esta aplicacao esta disponivel.

# Help:
#import pdb; pdb.set_trace()


# Versao: 0.1
#	-- Implementacao inicial - Recupera os sistemas implantados relacionando-os aos grupos
# Versao: 0.2
#	-- Mapeamento instancias - Recupera as instancias relacionando seu host e grupo
# Versao: 0.3
#   -- Criacao das classes
# Versao: 0.4
#   -- PortOffSet calculado e adicionado no objeto Instance.
#   -- Primeira versao funcional do programa.
#	-- TODO: Fazer com que o Deploy seja um objeto.
# Versao: 0.5
#	-- Programa gerando colecao de Groups com seus respectivos Deploys
#	-- Programa gerando colecao de Hosts com seus Groups e Instances
# Versao: 0.5.1
#	-- Correcao de um erro de duplicava os hosts

from org.jboss.as.cli.scriptsupport import CLI
import os
import getpass

############################################################ CONFIGURACOES #########################################################################

### AS VARIAVEIS A SEGUIR PODEM SER CONFIGURADAS PARA ACESSO PERSONALIZADOS.
## ALTERE AQUI O HOSTNAME DO DOMAIN CONTROLLER DA FARM EAP
host_eap = "apl7562lx033"
## ALTERE AQUI A PORTA DE CONEXAO PARA O CLI. 9999 EH O VALOR PADRAO.
port = 9999
## ESTE VALOR EH UTILIZADO PARA CALCULAR O PORT_OFFSET. A PARTIR DESTE VALOR EH SOMADO O PORT_OFFSET PARA APRESENTAR A PORTA DA INSTANCIA
default_port_http = 8080 # Default port http JBOSS EAP
## USUARIO DE ACESSO AO CLI
user = "admin"
## SENHA DE ACESSO AO CLI
password = getpass.getpass() # DESCOMENTE ESSA LINHA E COMENTE A SEGUINTE PARA QUE A SENHA SEJA PEDIDA NA EXECUCAO DO PROGRAMA

# Altere o home_jboss-cli para o diretório bin do seu EAP.
home_jboss_cli = "/home/p744574/Workspace/JBOSS/CONFIGURANDOEAP/EAP-6.0.1/jboss-eap-6.0/bin/"
#home_jboss_cli = "/usr/local/EAP-6.0.1/jboss-eap-6.0/bin/"

###################################################################################################################################################

cli = CLI.newInstance()
cli.connect(host_eap, port, user, password)

host_collection = []
deploy_collection = []


class Host:
	def __init__(self, hostname):
		self.hostname = hostname
		self.groups = []

	def __eq__(self,other):
		return (self.hostname == other.hostname)

	def add_group(self, group):
		self.groups.append(group)

	def find_group(self, group):
		for index in range(len(self.groups)):
			if self.groups[index] is not None and self.groups[index].name == group.name:
				break
		return index


class Group:
	def __init__(self, name):
		self.name = name
		self.instances = []
		self.deploys = []

	def __eq__(self, other):
		return (self.name == other.name)

	def add_instance(self, instance):
		self.instances.append(instance)

	def add_deploy(self, deploy):
		self.deploys.append(deploy)


class Instance:
	def __init__(self, name, port):
		self.port = port
		self.name = name


class Deploy:
	def __init__(self, name, active):
		self.name = name
		self.active = active
	


# Recebe o comando a ser executado no EAP via CLI
def execute_command(command):
	# Montando comando CLI
	command_eap = "%sjboss-cli.sh -c --controller=%s --user=admin --password=%s --commands="
	command_cli = command_eap%(home_jboss_cli,host_eap,password)
	return os.popen('%s"%s"'%(command_cli,command))


def execute_api_command(command):
	result = cli.cmd(command)
	response = result.getResponse()
	rs = response.get("result").asString()
	return rs


def list_hosts():
	hosts = execute_command("ls /host")
	for hostname in hosts:
		hostname = hostname.strip()
		yield Host(hostname)


# Este metodo recupera as instancias do host passado.
# Calcula o portoffset e retorna uma colecao de Instance
def list_instances(host):
	instances = execute_command("ls /host="+host+"/server-config")
	for name in instances:
		name = name.strip()
		rs_port = execute_command("/host="+host+"/server-config="+name+":read-attribute(name=socket-binding-port-offset)")
		rs_port = rs_port.read().strip()
		port_offset = ""
		for line in rs_port.splitlines():
			if 'result' in line:
				port_offset = line.split(" => ")[1].strip()
				if port_offset == "undefined":
					port_offset = 0
				else:
					port_offset = int(port_offset)
				break
		port = port_offset+default_port_http
		yield Instance(name,port)


def list_group(host, instance):
	group = Group(execute_api_command("/host="+host+"/server-config="+instance+":read-attribute(name=group)"))
	return group


# Retorna o indice da posicao da colecao onde for encontrado o objeto passado.
def find_collection_index(collection, obj):
	for index in range(len(collection)):
		if collection[index] == obj:
			return index


# Este metodo realiza um discovery mapeando os deploys e seus respectivos grupos.
# Captura os deploys habilitados ('enabled') em algum grupo 
# Utiliza tambem de um mecanismo para verificar se o grupo ja esta na colecao. Se o grupo ja existir o Deploy eh adicionado.
# se nao eh criado o grupo adicionado o deploy e entao o grupo eh adicionado a colecao.
def show_deploys_map():
	deploys = execute_command("deploy")
	deploys = deploys.read()
	group_collection = []
	for deploy in deploys.splitlines():
		info_deploy = execute_command("deployment-info --name="+deploy)
		info_deploy = info_deploy.read().strip()

		for line in info_deploy.splitlines():
			if 'enabled' in line:
				group = Group(line.split(" ")[0])
				dp = Deploy(deploy, True)
				if group in group_collection:
					group_collection[find_collection_index(group_collection, group)].add_deploy(dp)
				else:
					group.add_deploy(dp)
					group_collection.append(group)
	
	for group in group_collection:
		print "Group: " + group.name
		for deploy in group.deploys:
			print "		" + deploy.name + "			Enabled"

# Este metodo realiza um discovery na farm EAP vinculando todos os Host(s) a Group(s) e seus respectivas Instance(s)
def show_hosts_map():
	for host in list_hosts():
			#		import pdb; pdb.set_trace()
		for instance in list_instances(host.hostname):
			group = list_group(host.hostname, instance.name) 

#			import pdb; pdb.set_trace()
			host_index = find_collection_index(host_collection, host)
			if  host_index is not None and group in host_collection[host_index].groups:
				group_index = host_collection[find_collection_index(host_collection, host)].find_group(group)
				host_collection[find_collection_index(host_collection, host)].groups[group_index].add_instance(instance)
			else:
				group.add_instance(instance)
				if host in host_collection:
					host_collection[find_collection_index(host_collection, host)].add_group(group)
				else:
					host.add_group(group)
					host_collection.append(host)
			
	for host in host_collection:
		print "Host Name: " + host.hostname + "\n"
		for group in host.groups:
			print "   Group: " + group.name + "\n"
			for instance in group.instances:
				print "      Instance: " + instance.name + ":" + str(instance.port) + "\n"
		print 


if __name__ == "__main__":
	print "\n###################################################################################################\n"
	show_deploys_map()
	print "\n###################################################################################################\n"
	show_hosts_map()
