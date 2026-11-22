Local validation of the REPORT collection and cleanup fix, 22 Nov 2026. No AWS call: in-process fakes, sockets blocked.
- unittest.txt: final full run, 44 tests OK.
- unittest_first_run_1_failure.txt: the existing scoped-teardown test expected log groups deleted without a coverage
  check (the intended behaviour change); it now passes delete_log_groups='always'.
- unittest_second_run_calibration_flake.txt: TestCalibration failed on host timing; calibration_test_repeats.txt shows it
  fails occasionally on an unmodified HEAD copy too.
- selftest.txt, selftest_fake/: the whole live-test sequence on the fakes (000000000000 is the fakes' placeholder account).
- estimate_min_verification.json, plan_min_verification.txt: the smallest live verification (--records 4 --schedule 1024),
  its call plan and its estimate at UNVERIFIED prices.
- prior_run_coverage_counts.txt: the coverage check replayed on a scratch copy of run livetest_20261121-203051's records
  (counts only; the raw run folder was not written).
In the two failed-run transcripts the local repository path was replaced by <repo>. SHA256SUMS hashes the files as
written on Windows; SHA256SUMS.lf hashes the LF content that Git stores (core.autocrlf=true).
