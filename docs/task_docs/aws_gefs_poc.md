# AWS-based GEFS Data Processing POC Script

## Overview

Create a proof-of-concept script that runs on AWS to download and process GEFS precipitation ensemble data. The script will extract precipitation data for a Rhine basin point location across ensemble members, with resume capability for robust long-running execution.

## Problem Statement

- Need ensemble precipitation forecasts (21 members + spread + mean) for Rhine basin
- 5-7 day forecast horizon (120-168 hours, every 3 hours) is critical for hydropower planning
- Large dataset requires memory-efficient processing
- Script must be resumable for reliability over extended execution

## Solution Approach

Deploy a Python script on AWS EC2 that:

1. Downloads GEFS ensemble files sequentially (memory efficient)
2. Extracts total precipitation (`tp`) for specific Rhine basin point
3. Records forecast metadata (date, member, hour, value)
4. Deletes files immediately after processing
5. Implements robust checkpointing for resume capability

## Architecture

```
Local Machine → AWS EC2 (script execution) → NOAA GEFS S3 → Sequential Processing → CSV Output → Local Download
```

## Key Requirements

- **Scope**: 1 month of data (e.g., 2024-01-01 to 2024-01-31)
- **Cycle**: 00z only (midnight UTC)
- **Forecast hours**: 120, 123, 126, ..., 168 (5-7 days, 3-hour intervals)
- **Ensemble members**: 30 perturbed members (p01-p30) + control (c00) + spread ("gespr") + mean ("geavg")
- **Variable**: Total precipitation (`tp`) at Rhine basin point
- **Processing**: Sequential (download → extract → delete)
- **Resume**: Checkpoint-based recovery for interrupted execution

## Detailed Tasks

- [ ] Set up AWS environment and dependencies (EC2 instance, Python, libraries)
- [ ] Implement GEFS file discovery and URL generation
- [ ] Create sequential download and extraction pipeline
- [ ] Add Rhine basin point location extraction (single point tp values)
- [ ] Implement robust checkpointing system for resume capability
- [ ] Add comprehensive error handling (network, file corruption, API limits)
- [ ] Create CSV output format with metadata (date, member, hour, tp_value)
- [ ] Add progress tracking and estimated completion time
- [ ] Test with sample data (1-2 days) before full execution

## Success Criteria

- [ ] Script successfully processes 1 month of GEFS ensemble data
- [ ] Extracts tp values for 30 perturbed members + control + spread + mean across all forecast hours
- [ ] Processes ~22,000 files sequentially without memory issues
- [ ] Implements robust resume capability (can restart from any point)
- [ ] Output CSV contains complete dataset with proper metadata
- [ ] Execution time reasonable (days, not weeks) with progress tracking
- [ ] Handles network interruptions and API rate limits gracefully

## Deliverables

- [ ] Standalone Python script (`scripts/download_gefs_ensemble.py`)
- [ ] Requirements file with all necessary dependencies
- [ ] Checkpoint/progress tracking system
- [ ] Sample processed CSV output (1-2 days of data)
- [ ] Performance benchmarks and execution time estimates
- [ ] Resume/recovery documentation

## Technical Implementation Notes

**File Processing Pattern:**

```
for each_date in date_range:
    for each_member in ['c00', 'p01'-'p30', 'gespr', 'geavg']:
        for each_hour in [120, 123, 126, ..., 168]:
            download_file(date, member, hour)
            extract_tp_value(rhine_point)
            record_to_csv(date, member, hour, tp_value)
            delete_file()
            update_checkpoint()
```

**Resume Strategy:**

- JSON checkpoint file tracking last processed (date, member, hour)
- Atomic writes to prevent corruption
- Progress logging every N files

**Error Handling:**

- Exponential backoff for network failures
- Skip corrupted files with logging
- Resume from last successful checkpoint
