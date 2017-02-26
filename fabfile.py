from fabric.api import *

env.hosts = ['sp17-cs425-g15-0' + str(x) + '.cs.illinois.edu' for x in range(1, 6)]
env.user = 'sgupta80'

def deploy():
    with cd('/var/opt/mp1'):
        run('git pull')

def git():
    with cd('/var/opt/mp1'):
        run('git remote set-url origin git@gitlab.engr.illinois.edu:sgupta80/ece428-mp1.git')

