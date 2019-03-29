import pytest
import fairing
import sys
import io
import tempfile
import random

from google.cloud import storage
from fairing import TrainJob
from fairing.backends import KubernetesBackend, KubeflowBackend
from fairing.backends import KubeflowGKEBackend, GKEBackend, GCPManagedBackend

GCS_PROJECT_ID = fairing.cloud.gcp.guess_project_name()
TEST_GCS_BUCKET = '{}-fairing'.format(GCS_PROJECT_ID)
DOCKER_REGISTRY = 'gcr.io/{}'.format(GCS_PROJECT_ID)
GCS_SUCCESS_MSG = "gcs access is successful"
GCS_FAILED_MSG = 'google.api_core.exceptions.Forbidden: 403'
DUMMY_FN_MSG = "hello world"


# Training function that accesses GCS
def train_fn_with_gcs_access(temp_gcs_prefix):
    rnd_number = random.randint(0, 10**9)    
    gcs_filename = '{}/gcs_test_file_{}.txt'.format(temp_gcs_prefix, rnd_number)

    client = storage.Client()
    bucket_name = '{}-fairing'.format(client.project)
    bucket = client.get_bucket(bucket_name)

    # Upload file to GCS
    rnd_str = str(random.randint(0, 10**9))
    bucket.blob(gcs_filename).upload_from_string(rnd_str)

    # Download and read the file
    file_contents = bucket.blob(gcs_filename).download_as_string().decode("utf-8")
    if file_contents == rnd_str:
        print(GCS_SUCCESS_MSG)
    else:
        print("gcs content mismatch, expected:'{}' got: '{}'".format(rnd_str, file_contents))

# Update module to work with function preprocessor
# TODO: Remove when the function preprocessor works with functions from
# other modules.
train_fn_with_gcs_access.__module__ = '__main__'

def run_submission_with_gcs_access(deployer, pod_spec_mutators, namespace, gcs_prefix, capsys, expected_result):
    fairing.config.set_builder(
        'append', base_image='gcr.io/{}/fairing-test:latest'.format(GCS_PROJECT_ID),
        registry=DOCKER_REGISTRY, push=True)
    fairing.config.set_deployer(
        deployer, pod_spec_mutators=pod_spec_mutators, namespace=namespace)

    remote_train = fairing.config.fn(lambda : train_fn_with_gcs_access(gcs_prefix))
    remote_train()
    captured = capsys.readouterr()
    assert expected_result in captured.out

def test_job_submission_with_gcs_access(capsys, temp_gcs_prefix):
    run_submission_with_gcs_access(
        'job',
        pod_spec_mutators=[fairing.cloud.gcp.add_gcp_credentials],
        namespace='kubeflow',
        gcs_prefix=temp_gcs_prefix,
        capsys=capsys,
        expected_result=GCS_SUCCESS_MSG)

def test_tfjob_submission_with_gcs_access(capsys, temp_gcs_prefix):
    run_submission_with_gcs_access(
        'tfjob',
        pod_spec_mutators=[fairing.cloud.gcp.add_gcp_credentials],
        namespace='kubeflow',
        gcs_prefix=temp_gcs_prefix,
        capsys=capsys,
        expected_result=GCS_SUCCESS_MSG)

def test_job_submission_without_gcs_access(capsys, temp_gcs_prefix):
    run_submission_with_gcs_access(
        'job',
        pod_spec_mutators=[],
        namespace='kubeflow',
        gcs_prefix=temp_gcs_prefix,
        capsys=capsys,
        expected_result=GCS_FAILED_MSG)

def test_tfjob_submission_without_gcs_access(capsys, temp_gcs_prefix):
    run_submission_with_gcs_access(
        'tfjob',
        pod_spec_mutators=[],
        namespace='kubeflow',
        gcs_prefix=temp_gcs_prefix,
        capsys=capsys,
        expected_result=GCS_FAILED_MSG)

def test_job_submission_invalid_namespace(capsys, temp_gcs_prefix):
    with pytest.raises(ValueError) as err:
        run_submission_with_gcs_access(
            'job',
            pod_spec_mutators=[fairing.cloud.gcp.add_gcp_credentials],
            namespace='default',
            gcs_prefix=temp_gcs_prefix,
            capsys=capsys,
            expected_result=None)

    msg = 'Unable to mount credentials: '\
          'Secret user-gcp-sa not found in namespace default'
    assert msg in str(err.value)

def test_tfjob_submission_invalid_namespace(capsys, temp_gcs_prefix):
    with pytest.raises(ValueError) as err:
        run_submission_with_gcs_access(
            'tfjob',
            pod_spec_mutators=[fairing.cloud.gcp.add_gcp_credentials],
            namespace='default',
            gcs_prefix=temp_gcs_prefix,
            capsys=capsys,
            expected_result=None)

    msg = 'Unable to mount credentials: '\
          'Secret user-gcp-sa not found in namespace default'
    assert msg in str(err.value)
