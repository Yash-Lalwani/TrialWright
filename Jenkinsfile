pipeline {
  agent any
  environment {
    LLM_MODE = 'replay'
    IMAGE = "preflight-backend:${env.BUILD_NUMBER}"
  }
  stages {
    stage('Build') {
      steps {
        dir('backend') { sh 'uv sync --frozen' }
      }
    }
    stage('Test') {
      steps {
        dir('backend') {
          sh 'uv run ruff check .'
          sh 'uv run pytest -q'
        }
      }
    }
    stage('Image') {
      steps {
        sh 'docker build -f backend/Dockerfile -t $IMAGE .'
      }
    }
    stage('Push') {
      when { branch 'main' }
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry', usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          sh 'echo $REG_PASS | docker login -u $REG_USER --password-stdin $REGISTRY'
          sh 'docker tag $IMAGE $REGISTRY/preflight-backend:latest && docker push $REGISTRY/preflight-backend:latest'
        }
      }
    }
  }
}
