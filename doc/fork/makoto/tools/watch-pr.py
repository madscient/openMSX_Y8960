"""Shows what happened on upstream PR #2209 since the last recorded check.

    py doc/fork/makoto/tools/watch-pr.py                  # since the recorded check
    py doc/fork/makoto/tools/watch-pr.py <since> <head>   # re-read an older range

Run from the repository root, with an authenticated gh. When there is news,
it rewrites doc/fork/makoto/pr-watch-state.txt; commit that file together with
the record in implementation-plan.md. The second form never writes.
"""
import json
import subprocess
import sys

REPO, PR = "openMSX/openMSX", 2209
STATE = "doc/fork/makoto/pr-watch-state.txt"


def api(path):
    out = subprocess.run(["gh", "api", "--paginate", path], check=True,
                         capture_output=True, encoding="utf-8").stdout
    # --paginate concatenates one JSON document per page.
    decoder, pos, docs = json.JSONDecoder(), 0, []
    while pos < len(out):
        doc, end = decoder.raw_decode(out, pos)
        docs.append(doc)
        pos = end
        while pos < len(out) and out[pos].isspace():
            pos += 1
    if all(isinstance(d, list) for d in docs):
        return [item for d in docs for item in d]
    return docs[0]


def committed_state():
    # The committed copy, not the working file: a check that was never
    # recorded leaves the working file ahead, and its news must show again.
    shown = subprocess.run(["git", "show", f"HEAD:{STATE}"],
                           capture_output=True, encoding="utf-8")
    if shown.returncode != 0:
        sys.exit(f"{STATE} is not in HEAD; run this on the branch that holds "
                 "the Makoto plan (makoto-native-rate)")
    return dict(line.split("=", 1) for line in shown.stdout.split())


def stamp(item):
    # A review that is still pending has no time at all.
    return max(item.get(key) or "" for key in
               ("updated_at", "created_at", "submitted_at"))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) == 3:
        old = {"since": sys.argv[1], "head": sys.argv[2], "state": "open"}
    elif len(sys.argv) == 1:
        old = committed_state()
    else:
        sys.exit(__doc__)

    pr = api(f"repos/{REPO}/pulls/{PR}")
    commits = api(f"repos/{REPO}/pulls/{PR}/commits")
    threads = [
        ("comment", api(f"repos/{REPO}/issues/{PR}/comments")),
        ("review", api(f"repos/{REPO}/pulls/{PR}/reviews")),
        ("inline", api(f"repos/{REPO}/pulls/{PR}/comments")),
    ]

    state = "merged" if pr["merged"] else pr["state"]
    head = pr["head"]["sha"]
    print(f"PR #{PR} ({pr['html_url']}): {state}, head {head[:9]}")

    news = False
    if state != old["state"]:
        news = True
        print(f"\n*** STATE CHANGED: {old['state']} -> {state} ***")
        if state == "merged":
            print(f"Merged at {pr['merged_at']}. The plan says this branch is "
                  "dropped once the PR lands: tell the user.")

    shas = [c["sha"] for c in commits]
    matches = [s for s in shas if s.startswith(old["head"])]
    if not matches:
        news = True
        print(f"\nRecorded head {old['head'][:9]} is no longer in the PR "
              "(rebased or force-pushed); every commit is listed.")
        fresh = commits
    else:
        fresh = commits[shas.index(matches[0]) + 1:]
    if fresh:
        news = True
        print(f"\n== {len(fresh)} new commit(s) ==")
        for c in fresh:
            print(c["sha"][:9], c["commit"]["committer"]["date"],
                  c["commit"]["message"].splitlines()[0])
        print(f"(git fetch upstream pull/{PR}/head, then diff "
              f"{old['head'][:9]}..{head[:9]})")

    latest = old["since"]
    for kind, items in threads:
        for item in items:
            when = stamp(item)
            latest = max(latest, when)
            if when <= old["since"]:
                continue
            news = True
            where = ""
            if kind == "inline":
                line = item.get("line") or item.get("original_line")
                where = f" {item['path']}:{line}"
                if item.get("in_reply_to_id"):
                    where += f" (reply to {item['in_reply_to_id']})"
            elif kind == "review":
                where = f" {item['state']}"
            print(f"\n== {kind} {item['id']} by {item['user']['login']} "
                  f"at {when}{where} ==")
            print(item.get("html_url", ""))
            if item.get("body"):
                print(item["body"])

    if not news:
        print(f"\nNo news since {old['since']}.")
        return
    new = f"since={latest}\nhead={head}\nstate={state}\n"
    if len(sys.argv) == 3:
        print("\nRange given on the command line; state file left alone.")
        return
    with open(STATE, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print(f"\n{STATE} rewritten. Record the above in implementation-plan.md "
          "and commit both.")


if __name__ == "__main__":
    main()
