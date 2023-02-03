# Ansible Collection - cbsch.domeneshop

## Requirements

The module requires the [Domeneshop python module](https://pypi.org/project/domeneshop/)

The version tested is `0.4.2`

## Installation

Install from galaxy
```bash
ansible-galaxy collection install cbsch.domeneshop
```

You might also have to install the domeneshop Python module
```bash
python3 -m pip install domeneshop
```

## Example usage

Most basic usage.

```yml
- hosts: localhost
  tasks:
  - name: Update DNS records
    cbsch.domeneshop.dns:
        domain: example.com
        host: www
        ttl: 3600
        type: A
        data: 10.0.0.100
        apikey: "{{ domeneshop_apikey }}"
        apisecret : "{{ domeneshop_apisecret }}"
```

Set authentication details in environment. Useful when running multiple tasks.

```yml
- hosts: localhost
  tasks:
  - name: Update DNS records
    cbsch.domeneshop.dns:
      domain: example.com
      host: www
      ttl: 3600
      type: A
      data: 10.0.0.100

  environment:
    DOMENESHOP_APIKEY: '{{ domeneshop_apikey }}'
    DOMENESHOP_APISECRET: '{{ domeneshop_apisecret }}'
```

Update multiple records on a single domain name, and caching records in /tmp to speed things up.

```yml
- hosts: localhost
  tasks:
    name: Update DNS records
    cbsch.domeneshop.dns:
      domain: example.com
      host: "{{ item.host }}"
      ttl: 3600
      type: A
      data: 10.0.0.100
      usecache: true
    loop:
    - host: www
    - host: ftp
    - host: ssh

  environment:
    DOMENESHOP_APIKEY: '{{ domeneshop_apikey }}'
    DOMENESHOP_APISECRET: '{{ domeneshop_apisecret }}'
```

## Running on docker

Quick guide to running the collection using docker. Replace values in the playbook with your own.

The example commands will also work on a normal Ubuntu machine.

```bash
docker run -it --rm ubuntu /bin/bash
# Inside the container
apt update
apt install -y python3 python3-pip
python3 -m pip install ansible
python3 -m pip install domeneshop
ansible-galaxy collection install cbsch.domeneshop
cd ~
mkdir ansible
cd ansible
cat << EOF > playbook.yml
- hosts: localhost
  tasks:
  - name: Update DNS records
    cbsch.domeneshop.dns:
        domain: example.com
        host: www
        ttl: 3600
        type: A
        data: 10.0.0.100
        apikey: "domeneshop_api_key"
        apisecret : "domeneshop_api_key"
EOF
ansible-playbook playbook.yml --check --diff

```
