#!/usr/bin/expect -f

# Expect script. Expect Reference: https://linux.die.net/man/1/expect

set timeout 10

# Cleanup previous runs
spawn rm -f /tmp/trigger-1 /tmp/trigger-2
interact

# Get version
spawn foremon --version
expect EOF

# Start Test 1

# will trigger test2 later
spawn bash -c "sleep 4; touch /tmp/EXPECT_TEST2"

spawn foremon -V -f config/sanity-check.toml -a test1 -a test2
expect_after eof {
    send_user "\n[exec date +%s] - DONE - SUCCESS\n"
    exit 0
}

send_user "\n[exec date +%s] - WORKING - Waiting for initial tasks to execute ...\n"
expect "starting"
expect "trigger-1"
expect "clean exit"
expect "clean exit" {
    send_user "\n[exec date +%s] - WORKING - Sending RESTART\n"
    send "rs\n"
}

send_user "\n[exec date +%s] - WORKING - Waiting for restarted tasks to execute ...\n"
expect "starting"
expect "starting"
expect "trigger*"
expect "trigger*"
expect "clean exit*"
expect "clean exit*"

send_user "\n[exec date +%s] - WORKING - Waiting for file change event ...\n"
expect {
    "timeout" {
        send_user "\n[exec date +%s] - FAIL - while waiting for filesystem event to fire\n"
        exit 1
    }

    "*/tmp/EXPECT_TEST2 was modified"
}
expect "starting*"
expect "trigger-2"

expect "clean exit*" {
    send_user "\n[exec date +%s] - WORKING - Sending exit command ...\n"
    send "exit\n"
    expect "stopping..."

    "timeout" {
        send_user "\n[exec date +%s] - FAIL - foremon did not behave as expected\n"
        exit 1
    }
}

expect EOF
