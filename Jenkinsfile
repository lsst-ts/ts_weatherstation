properties(
    [
    buildDiscarder
        (logRotator (
            artifactDaysToKeepStr: '',
            artifactNumToKeepStr: '',
            daysToKeepStr: '14',
            numToKeepStr: '10'
        ) ),
    disableConcurrentBuilds()
    ]
)
pipeline {
    agent any
    environment {
        container_name = "c_${BUILD_ID}_${JENKINS_NODE_COOKIE}"
        user_ci = credentials('lsst-io')
        work_branches = "${GIT_BRANCH} ${CHANGE_BRANCH} develop"
    }
    stages {
        stage("Pulling image.") {
            steps {
                script {
                    sh """
                    docker pull lsstts/salobj:develop
                    """
                }
            }
        }
        stage("Start container") {
            steps {
                script {
                    sh """
                    chmod -R a+rw \${WORKSPACE}
                    container=\$(docker run -v \${WORKSPACE}:/home/saluser/repo/ -td --rm --name \${container_name} -e LTD_USERNAME=\${user_ci_USR} -e LTD_PASSWORD=\${user_ci_PSW} lsstts/salobj:develop)
                    """
                }
            }
        }
        stage("Checkout sal") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_sal && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Checkout salobj") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_salobj && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Checkout xml") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_xml && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Checkout IDL") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_idl && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Build IDL files") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && setup ts_sal -t current && make_idl_files.py WeatherStation\"
                    """
                }
            }
        }
        stage("Checkout config_ocs") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_config_ocs/ && /home/saluser/.checkout_repo.sh \${work_branches} \"
                    """
                }
            }
        }
        stage("Running tests") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd repo && eups declare -r . -t saluser && setup ts_weatherstation -t saluser && export LSST_DDS_IP=192.168.0.1 && pytest --color=no -ra --junitxml=tests/results/results.xml\"
                    """
                }
            }
        }
    }
    post {
        always {
            // The path of xml needed by JUnit is relative to
            // the workspace.
            junit 'tests/results/results.xml'
         }
        cleanup {
            sh """
                docker exec -u root --privileged \${container_name} sh -c \"chmod -R a+rw /home/saluser/repo/ \"
                docker stop \${container_name}
            """
            deleteDir()
        }
    }
}
