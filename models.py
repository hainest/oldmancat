from django.db import models
from django.db.models import Count
from taggit.managers import TaggableManager
from itertools import chain

from .utils import TEST_RUN_STATUS, TEST_BUILD_STATUS, TEST_RESULT_STATUS, TEST_MODES, LANGUAGES, get_upload_folder
from .storage import OverwriteStorage

import json


class PullRequest(models.Model):
    """
    A PullRequest holds the URL and username of a pull request for reference
    """
    url = models.TextField(blank=False, null=False)
    user = models.TextField(blank=False, null=False)
    github_id = models.PositiveIntegerField(blank=True, null=False)

    def __str__(self):
        return "[pull_request|%s]" % self.url

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"
        unique_together = (("url", "user", "github_id"),)


class Compiler(models.Model):
    name = models.CharField(blank=False, null=False, max_length=100, unique=True)
    version = models.CharField(blank=True, null=False, max_length=100)
    path = models.CharField(blank=True, null=True, max_length=100)
    language = models.CharField(choices=LANGUAGES, blank=True, null=True, max_length=100, unique=True)

    def __str__(self):
        return "[compiler:%s@%s]" % (self.name, self.version)

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"
        unique_together = (
            ("name", "version", "path", "language"),
        )



class TestMode(models.Model):
    name = models.CharField(choices=TEST_MODES, blank=False, null=False, max_length=25, unique=True)

    def __str__(self):
        return "[test-mode|%s]" % self.name

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"

class Dependency(models.Model):
    name = models.CharField(max_length=250, blank=False, null=False)
    version = models.CharField(max_length=100, blank=False, null=False)
    path = models.CharField(blank=True, null=True, max_length=100)

    def __str__(self):
        return "[dependency|%s@%s]" % (self.name, self.version)

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"
        unique_together = (("name", "version"),)


class TestRunResult(models.Model):
    dyninst_build = models.ForeignKey("main.BuildResults", null=False, blank=False, on_delete=models.CASCADE)
    testsuite_build = models.ForeignKey("main.BuildResults", null=False, blank=False, on_delete=models.CASCADE)
    test_run_status = models.CharField(choices=TEST_RUN_STATUS, default="NOTRUN", blank=False, null=False, max_length=25)
    is_single_step = models.BooleanField(blank=True, null=True)
    num_parallel_tests = models.PositiveIntegerField(default=0, blank=True)
    num_omp_threads = models.PositiveIntegerField(default=0, blank=True)
    time = models.PositiveIntegerField(default=0, blank=True)
    test_log = models.FileField(upload_to=get_upload_folder, max_length=255, storage=OverwriteStorage())

    def __str__(self):
        return "[test-run-result|%s]" % self.id

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"


class BuildResults(models.Model):
    status = models.CharField(choices=TEST_BUILD_STATUS, default="OK", blank=False, null=False, max_length=25)
    num_jobs = models.PositiveIntegerField(default=0, blank=True)
    time = models.PositiveIntegerField(default=0, blank=True)
    log = models.FileField(upload_to=get_upload_folder, max_length=255, storage=OverwriteStorage(), blank=True)

    def __str__(self):
        return "[build-result|%s]" % self.id

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"


class Environment(models.Model):
    hostname = models.CharField(max_length=150, blank=False, null=False)
    arch = models.CharField(max_length=50, blank=False, null=False)
    host_os = models.CharField(max_length=150, blank=False, null=False)
    kernel = models.CharField(max_length=150, blank=False, null=False)

    dependencies = models.ManyToManyField(
        "main.Dependency",
        blank=True,
        default=None,
        related_name="dependencies",
        related_query_name="dependencies",
    )

    def __str__(self):
        return "[environment|%s]" % self.arch

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"
        unique_together = (
            ("hostname", "arch", "host_os", "kernel"),
        )


class RepositoryState(models.Model):
    name = models.CharField(max_length=100, blank=False, null=False)
    commit = models.CharField(max_length=50, blank=False, null=False)
    branch = models.CharField(max_length=100, blank=False, null=False)
    history = models.TextField(blank=True, null=True)

    def __str__(self):
        return "[repository:%s|%s]" % (self.name, self.commit)

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"
        unique_together = (("name", "commit", "branch",))


class TestRun(models.Model):
    """A TestRun is a single test run result
    """
    date_created = models.DateTimeField("date created", auto_now_add=True)
    dyninst = models.ForeignKey("main.RepositoryState", null=False, blank=False, on_delete=models.CASCADE, related_name="testrun_dyninst")
    testsuite = models.ForeignKey("main.RepositoryState", null=False, blank=False, on_delete=models.CASCADE, related_name="testrun_testsuite")
    environment = models.ForeignKey("main.Environment", null=False, blank=False, on_delete=models.CASCADE)
    pull_request = models.ForeignKey("main.PullRequest", null=True, blank=True, on_delete=models.CASCADE)
    cirun_url = models.CharField(max_length=250, blank=True, null=True)
    compiler = models.ForeignKey("main.Compiler", null=False, blank=False, on_delete=models.CASCADE)
    result = models.ForeignKey("main.TestRunResult", null=True, blank=True, on_delete=models.CASCADE)
    command = models.TextField()

    def __str__(self):
        return "[testrun:%s]" % self.id

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"
        unique_together = (("dyninst", "testsuite", "environment", "compiler"),)
 
class TestResult(models.Model):
    run = models.ForeignKey("main.TestRun", null=False, blank=False, on_delete=models.CASCADE)
    name = models.CharField(max_length=150, blank=False, null=False)
    compiler = models.ForeignKey("main.Compiler", null=False, blank=False, on_delete=models.CASCADE)
    test_mode = models.ForeignKey("main.TestMode", null=False, blank=False, on_delete=models.CASCADE)

    isPIC = models.BooleanField(default=False)
    is64bit = models.BooleanField(default=False)
    isDynamic = models.BooleanField(default=False)

    reason = models.TextField()
    optimization = models.CharField(max_length=150, blank=False, null=False)
    status = models.CharField(choices=TEST_RESULT_STATUS, default="NOSTATUS", blank=False, null=False, max_length=25)
    threading = models.TextField()
    
    def __str__(self):
        return "[test-result for %s:%s]" % (self.run.id, self.name)

    def __repr__(self):
        return str(self)

    @property
    def isStatus(self):
        return not self.isDynamic

    class Meta:
        app_label = "main"
        unique_together = (
            ("name", "run", "compiler", "test_mode"),
        )


class Regressions(models.Model):
    previous_run = models.ForeignKey("main.TestRun", null=False, blank=False, on_delete=models.CASCADE, related_name="regressions_previous_run")
    current_run = models.ForeignKey("main.TestRun", null=False, blank=False, on_delete=models.CASCADE, related_name="regressions_current_run")
    count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "[regressions:%s to %s]" % (self.previous_run.id, self.current_run.id)

    def __repr__(self):
        return str(self)

    class Meta:
        app_label = "main"
        unique_together = (
            ("previous_run", "current_run",),
        )
