from fabric.api import *

s = 'sp17-cs425-g15-{:02d}.cs.illinois.edu'

env.hosts = [s.format(x) for x in range(1, 11)]
env.user = 'sgupta80'

def deploy():
    with cd('/var/opt/mp1'):
        run('git pull')

def git():
    with cd('/var/opt/mp1'):
        run('git remote set-url origin git@gitlab.engr.illinois.edu:sgupta80/ece428-mp1.git')
