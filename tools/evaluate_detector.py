#!/usr/bin/env python
"""Sequential image-level evaluation; no training or camera/backend operations.

Scoring: contaminated requires contamination_suspected AND RED/AMBER. A GREY
contamination is a separately reported low-confidence miss. Healthy requires
no_contamination_seen/GREEN. Negative requires no_detection/GREY. Errors are
unavailable, excluded from accuracy/latency, and never scored as correct.
"""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean
import sys

# Support both `python tools/evaluate_detector.py` and module imports.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detectors.types import DetectionBox, DetectionResult
from live_camera import DEFAULT_WEIGHTS, build_detector, summarize_detections

CATEGORIES = ('healthy', 'contaminated', 'negative')
EXTENSIONS = frozenset(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'))
FIELDS = ('path', 'expected', 'provider', 'model_id', 'verdict', 'severity',
          'n_healthy', 'n_contaminated', 'max_conf', 'max_contaminated_conf',
          'inference_ms', 'correct', 'outcome', 'error')


def discover_images(dataset):
    root = Path(dataset)
    if not root.is_dir():
        raise ValueError('Dataset directory does not exist')
    missing = [name for name in CATEGORIES if not (root / name).is_dir()]
    if missing:
        raise ValueError('Dataset requires healthy/, contaminated/, negative/ directories')
    return sorted(((p, category) for category in CATEGORIES
                   for p in (root / category).rglob('*')
                   if p.is_file() and p.suffix.lower() in EXTENSIONS),
                  key=lambda item: item[0].relative_to(root).as_posix())


def score(expected, summary):
    """Return correctness and explicit image-level outcome, never box mAP."""
    verdict, severity = summary['verdict'], summary['severity']
    if expected == 'contaminated':
        if verdict == 'contamination_suspected' and severity in ('RED', 'AMBER'):
            return True, 'contamination_detected'
        if verdict == 'contamination_suspected':
            return False, 'low_confidence_contamination_miss'
        return False, 'contamination_miss'
    if expected == 'healthy':
        if verdict == 'no_contamination_seen' and severity == 'GREEN':
            return True, 'healthy_correct'
        if verdict == 'contamination_suspected':
            return False, 'healthy_false_alert'
        return False, 'healthy_not_detected'
    if expected == 'negative':
        if verdict == 'no_detection' and severity == 'GREY':
            return True, 'negative_correct'
        return False, ('negative_contamination_false_alert' if verdict == 'contamination_suspected'
                       else 'negative_healthy_false_claim')
    raise ValueError('Unknown expected category')


def validate_result(result):
    """Reject malformed normalized output as a whole before scoring Healthy."""
    if not isinstance(result, DetectionResult) or not isinstance(result.boxes, list):
        raise ValueError('Invalid detection result')
    if isinstance(result.inference_ms, bool) or not math.isfinite(result.inference_ms) or result.inference_ms < 0:
        raise ValueError('Invalid latency')
    for box in result.boxes:
        if (not isinstance(box, DetectionBox) or not isinstance(box.label, str)
                or not box.label.strip() or isinstance(box.confidence, bool)
                or not math.isfinite(box.confidence) or not 0 <= box.confidence <= 1
                or len(box.xyxy) != 4 or not all(math.isfinite(v) for v in box.xyxy)
                or box.xyxy[2] <= box.xyxy[0] or box.xyxy[3] <= box.xyxy[1]):
            raise ValueError('Invalid detection box')


def evaluate(images, detector, provider, read_image):
    """One detect per readable image, in order, with no concurrency/retries."""
    rows = []
    for path, expected in images:
        row = dict.fromkeys(FIELDS, '')
        row.update(path=str(path), expected=expected, provider=provider,
                   verdict='no_detection', severity='GREY', n_healthy=0,
                   n_contaminated=0, max_conf=0.0, max_contaminated_conf=0.0,
                   outcome='unavailable')
        try:
            frame = read_image(str(path))
            if frame is None or frame.size == 0:
                row['error'] = 'unreadable_image'
                rows.append(row)
                continue
        except Exception:
            row['error'] = 'unreadable_image'
            rows.append(row)
            continue
        try:
            result = detector.detect(frame)
        except Exception:
            # SDK exceptions may contain credentials: never emit their text.
            row['error'] = 'provider_unavailable'
            rows.append(row)
            continue
        try:
            validate_result(result)
            summary = summarize_detections(result.boxes)
            correct, outcome = score(expected, summary)
            row.update({key: summary[key] for key in (
                'verdict', 'severity', 'n_healthy', 'n_contaminated',
                'max_conf', 'max_contaminated_conf')})
            row.update(model_id=result.model_id, inference_ms=result.inference_ms,
                       correct=correct, outcome=outcome)
        except Exception:
            row['error'] = 'malformed_result'
        rows.append(row)
    return rows


def aggregate(rows):
    successful = [r for r in rows if not r['error']]
    latencies = sorted(r['inference_ms'] for r in successful)
    correct = sum(r['correct'] for r in successful)
    outcomes = [r['outcome'] for r in successful]
    return dict(total_images=len(rows), successfully_inspected=len(successful),
                unavailable_error=len(rows)-len(successful), correct=correct,
                incorrect=len(successful)-correct,
                accuracy=correct/len(successful) if successful else None,
                healthy_false_alerts=outcomes.count('healthy_false_alert'),
                contamination_misses=sum(o in ('contamination_miss', 'low_confidence_contamination_miss') for o in outcomes),
                low_confidence_contamination_misses=outcomes.count('low_confidence_contamination_miss'),
                negative_scene_false_claims=sum(o.startswith('negative_') and o != 'negative_correct' for o in outcomes),
                negative_contamination_false_alerts=outcomes.count('negative_contamination_false_alert'),
                no_detection_count=sum(r['verdict']=='no_detection' for r in successful),
                average_inference_ms=mean(latencies) if latencies else None,
                p95_inference_ms=latencies[math.ceil(.95*len(latencies))-1] if latencies else None)


def write_csv(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', '--data', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--model-provider', choices=('local', 'roboflow'), default='local')
    parser.add_argument('--weights', default=DEFAULT_WEIGHTS)
    parser.add_argument('--conf', type=float, default=.4)
    parser.add_argument('--imgsz', type=int, default=416)
    parser.add_argument('--device', default=None)
    parser.add_argument('--roboflow-model-id', default='contamination-detection-ozkwx/1')
    parser.add_argument('--roboflow-api-url', default='https://serverless.roboflow.com')
    args = parser.parse_args(argv)
    if not math.isfinite(args.conf) or not 0 <= args.conf <= 1 or args.imgsz <= 0:
        parser.error('--conf must be finite in [0,1]; --imgsz must be positive')
    if args.output.suffix.lower() != '.csv':
        parser.error('--output must end in .csv')
    from urllib.parse import urlsplit
    endpoint = urlsplit(args.roboflow_api_url)
    if (not args.roboflow_model_id.strip() or endpoint.scheme not in ('http','https')
            or not endpoint.netloc or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment):
        parser.error('Invalid hosted model/endpoint configuration')
    return args


def main(argv=None):
    args = parse_args(argv)
    images = discover_images(args.dataset)
    if images:
        import cv2
        detector = build_detector(args)
        try:
            rows = evaluate(images, detector, args.model_provider,
                            lambda path: cv2.imread(path, cv2.IMREAD_COLOR))
        finally:
            detector.close()
    else:
        rows = []  # No model load/paid calls for empty datasets.
    write_csv(args.output, rows)
    print(json.dumps(aggregate(rows), indent=2, allow_nan=False))
    print('Image-level metrics only: review contamination misses, false alerts and unavailable counts; accuracy alone is insufficient.')
    if not images:
        print('No evaluation images found; no model-quality conclusion can be made.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, ImportError, RuntimeError):
        raise SystemExit('Evaluation failed: check dataset, output path, provider configuration and dependencies.') from None
