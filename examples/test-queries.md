# Testing Issue Tracking Agent - Query Examples

This document provides test cases for the `issue-tracking` agent to verify all query types work correctly.

## Setup

Before testing, ensure you have:
1. GitHub CLI installed and authenticated (`gh auth status`)
2. Access to `microsoft-amplifier/amplifier-shared` repo
3. Some test issues created and synced

## Test Data Setup

Create diverse test data to exercise all query patterns:

```
# In an Amplifier session with the issues bundle active
> Create an issue titled "Refactor session analyzer" with description "Reduce memory footprint" and area core, priority high, assign to robotdad

> Create an issue titled "Update bundle documentation" with description "Add examples for bundle composition" and area foundation, priority normal, assign to malicata

> Create an issue titled "Add PostgreSQL support" with description "Enable postgres backend for issue storage" and area modules, priority high, assign to contributor1

> Create an issue titled "Fix event logging race condition" with description "Race condition in event writer" and area core, priority critical, assign to robotdad

> Create an issue titled "Design new CLI commands" with description "Improve user experience" and area cli, priority low

> Sync all issues to GitHub
```

Mark some as in-progress or blocked:
```
> Update issue [issue_id] status to in_progress
> Update issue [issue_id] status to blocked
```

Close one or two:
```
> Close issue [issue_id] with reason "Completed refactoring, 60% memory reduction"
```

## Query Test Cases

### Test 1: What issues are currently open?

**Query:**
```
> Use the issue-tracking agent to tell me what issues are currently open
```

**Expected Response:**
- List of open issues
- Grouped by status (open, in-progress, blocked)
- Includes assignees
- Links to GitHub issues

**Validation:**
- Count matches actual open issues
- All statuses represented
- GitHub links are valid

---

### Test 2: Who worked on Core?

**Query:**
```
> Use the issue-tracking agent to show me who worked on Core
```

**Expected Response:**
- List of unique assignees who touched area:core issues
- What each person worked on
- Current status of their issues
- Links to relevant issues

**Validation:**
- Only shows users who worked on area:core
- Includes both open and closed core issues
- Assignees match actual data

---

### Test 3: What's blocked?

**Query:**
```
> Use the issue-tracking agent to show me what's blocked
```

**Expected Response:**
- List of issues with status:blocked
- Blocking reasons if available
- Who's assigned
- Suggestions for follow-up

**Validation:**
- Only shows blocked issues
- Provides actionable context
- Links to issues

---

### Test 4: What did we accomplish last week?

**Query:**
```
> Use the issue-tracking agent to tell me what we accomplished last week
```

**Expected Response:**
- Closed issues from the last 7 days
- Grouped by assignee
- Summary of accomplishments
- Highlights (high priority completions)
- Date range specified

**Validation:**
- Only includes closed issues
- Date filtering works correctly
- Summary is accurate
- Grouped by person

---

### Test 5: Duplicate detection

**Query:**
```
> Use the issue-tracking agent to check if anyone is working on something similar to "optimize session performance"
```

**Expected Response:**
- Semantic comparison against existing issues
- List of similar issues with similarity reasoning
- Status of similar issues
- Recommendation (collaborate vs create new)

**Validation:**
- Finds semantically similar issues
- Explains why they're similar
- Provides actionable recommendation

---

### Test 6: Specific issue details

**Query:**
```
> Use the issue-tracking agent to tell me about issue #42
```

**Expected Response:**
- Issue title and description
- Current status
- Assignee
- Labels (area, priority, status)
- Timeline (created, updated, closed)
- Link to GitHub

**Validation:**
- Fetches correct issue
- All metadata present
- Formatted clearly

---

### Test 7: What's the status across the team?

**Query:**
```
> Use the issue-tracking agent to give me an overview of what the team is working on
```

**Expected Response:**
- Summary of all open issues
- Breakdown by status (open, in-progress, blocked)
- Breakdown by area (core, foundation, etc.)
- Who's working on what
- Any blockers or high-priority items

**Validation:**
- Comprehensive overview
- Multiple groupings (status, area, person)
- Actionable insights

---

### Test 8: Priority-focused query

**Query:**
```
> Use the issue-tracking agent to show me all critical and high priority issues
```

**Expected Response:**
- Issues with priority:critical or priority:high labels
- Current status
- Who's assigned
- Ordered by priority

**Validation:**
- Only shows high-priority issues
- Sorted appropriately
- Clear priority indicators

---

## Integration Tests

### End-to-End Workflow

1. **Create local issue:**
   ```
   > Create an issue to test the full workflow
   ```

2. **Sync to GitHub:**
   ```
   > Sync my issues to GitHub
   ```

3. **Query via agent:**
   ```
   > Use issue-tracking agent to find my recent issue
   ```

4. **Verify link:**
   - Click GitHub URL in response
   - Confirm issue exists with correct labels
   - Verify local issue has github_issue_number in metadata

5. **Update and re-query:**
   ```
   > Update issue [id] to in-progress
   > Sync to GitHub
   > Use issue-tracking agent to show in-progress items
   ```

6. **Close and verify:**
   ```
   > Close issue [id]
   > Sync to GitHub (with include_closed=true)
   > Use issue-tracking agent to show what we accomplished today
   ```

---

## Expected Behavior

### Agent Delegation
- Main agent should delegate to issue-tracking agent via task tool
- No interruption to main conversation flow
- Results returned clearly formatted

### Error Handling
- Graceful handling if repo is empty
- Clear message if gh CLI not authenticated
- Helpful error if labels don't exist

### Performance
- Queries should complete in <5 seconds for repos with <100 issues
- Responses should be concise (not dumping raw JSON)

---

## Common Issues & Solutions

### Issue: "gh: command not found"
**Solution:** Install GitHub CLI
```bash
# macOS
brew install gh

# Linux
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

### Issue: "gh auth status" fails
**Solution:** Authenticate with GitHub
```bash
gh auth login
# Follow prompts
```

### Issue: Labels don't exist in repo
**Solution:** Create labels manually or via script
```bash
# Create standard labels
gh label create "status:open" --repo microsoft-amplifier/amplifier-shared
gh label create "status:in-progress" --repo microsoft-amplifier/amplifier-shared
gh label create "status:blocked" --repo microsoft-amplifier/amplifier-shared
gh label create "status:closed" --repo microsoft-amplifier/amplifier-shared
gh label create "priority:critical" --repo microsoft-amplifier/amplifier-shared
gh label create "priority:high" --repo microsoft-amplifier/amplifier-shared
gh label create "priority:normal" --repo microsoft-amplifier/amplifier-shared
gh label create "priority:low" --repo microsoft-amplifier/amplifier-shared
gh label create "area:core" --repo microsoft-amplifier/amplifier-shared
gh label create "area:foundation" --repo microsoft-amplifier/amplifier-shared
gh label create "area:bundles" --repo microsoft-amplifier/amplifier-shared
gh label create "area:modules" --repo microsoft-amplifier/amplifier-shared
```

### Issue: Agent not found
**Solution:** Verify bundle registration
```bash
# Check bundle.md has agent registered
cat bundle.md | grep -A 3 agents:
```

---

## Success Criteria

After testing all queries, you should have verified:

✅ All query patterns return accurate results  
✅ Duplicate detection finds similar issues  
✅ Date filtering works correctly  
✅ Results are grouped/formatted clearly  
✅ GitHub links are valid and clickable  
✅ Agent delegation works smoothly  
✅ Error messages are helpful  
✅ Performance is acceptable  

---

## Next Steps After Testing

Once all tests pass:
1. Document any edge cases discovered
2. Update agent instructions if needed
3. Create label setup script for new repos
4. Add real-world usage examples to README
