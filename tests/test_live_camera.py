"""Hardware-independent live camera regression tests (standard library only)."""
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import live_camera as live


def result(labels, confs):
    tensor = lambda values: SimpleNamespace(tolist=lambda: values)
    return SimpleNamespace(names=dict(enumerate(labels)), boxes=SimpleNamespace(
        cls=tensor(list(range(len(labels)))), conf=tensor(confs),
        xyxy=tensor([[10, 20, 30, 40] for _ in labels])))


class VerdictTests(unittest.TestCase):
    def test_red(self):
        s = live.summarize_result(result(["Contaminated"], [0.80]))
        self.assertEqual((s["verdict"], s["message"], s["severity"]),
                         ("contamination_suspected", "Possible contamination", "RED"))

    def test_amber_and_healthy_confidence(self):
        s = live.summarize_result(result(["Healthy", "Contaminated"], [0.99, 0.63]))
        self.assertEqual(s["severity"], "AMBER")
        self.assertEqual(s["max_conf"], 0.99)
        self.assertEqual(s["max_contaminated_conf"], 0.63)
        self.assertEqual((s["n_contaminated"], s["n_healthy"]), (1, 1))
        self.assertEqual(s["boxes"][0]["xyxy"], [10, 20, 30, 40])

    def test_amber_boundary(self):
        self.assertEqual(live.summarize_result(result(["Contaminated"], [0.4]))["severity"], "AMBER")

    def test_green(self):
        s = live.summarize_result(result(["Healthy"], [0.99]))
        self.assertEqual((s["verdict"], s["message"], s["severity"]),
                         ("no_contamination_seen", "No contamination seen", "GREEN"))

    def test_grey(self):
        for r in (None, result([], []), result(["Unrelated"], [0.99]), SimpleNamespace(boxes=None)):
            s = live.summarize_result(r)
            self.assertEqual((s["verdict"], s["message"], s["severity"]),
                             ("no_detection", "Could not inspect", "GREY"))

    def test_low_contamination_never_green(self):
        s = live.summarize_result(result(["Healthy", "Contaminated"], [0.99, 0.3]))
        self.assertEqual(s["verdict"], "contamination_suspected")
        self.assertEqual(s["severity"], "GREY")

    def test_arguments(self):
        args = live.parse_args([])
        self.assertEqual((args.cam, args.conf, args.fps, args.device), (0, 0.4, 5, None))
        for flag, value in (("--fps", "0"), ("--fps", "nan"), ("--conf", "1.1")):
            with self.assertRaises(SystemExit), patch("sys.stderr"):
                live.parse_args([flag, value])

    def test_prediction_options(self):
        model, frame = MagicMock(), MagicMock()
        frame.shape = (480, 640, 3)
        model.predict.return_value = [result(["Healthy"], [0.9])]
        live.infer(model, frame, live.parse_args(["--device", "cpu"]))
        model.predict.assert_called_once_with(frame, conf=0.4, imgsz=416, verbose=False, device="cpu")


class CameraTests(unittest.TestCase):
    def run_case(self, failure=None, opened=True):
        cv2, factory = MagicMock(), MagicMock()
        camera = cv2.VideoCapture.return_value
        camera.isOpened.return_value = opened
        camera.read.return_value = (True, MagicMock())
        if failure is not None:
            camera.read.side_effect = failure
        cv2.waitKey.return_value = ord("q")
        with patch.object(live, "draw_overlay", side_effect=lambda cv, frame, *a: frame), \
                patch.object(live, "ThreadPoolExecutor") as pool:
            if failure is not None and not isinstance(failure, KeyboardInterrupt) or not opened:
                with self.assertRaises(RuntimeError):
                    live.run_camera(live.parse_args([]), cv2, factory)
            else:
                live.run_camera(live.parse_args([]), cv2, factory)
            if opened:
                pool.return_value.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
        camera.release.assert_called_once()
        cv2.destroyAllWindows.assert_called_once()
        factory.assert_called_once_with(live.DEFAULT_WEIGHTS)
        cv2.VideoCapture.assert_called_once_with(0)

    def test_quit_cleanup(self):
        self.run_case()

    def test_exception_cleanup(self):
        self.run_case(RuntimeError("camera failed"))

    def test_ctrl_c_cleanup(self):
        self.run_case(KeyboardInterrupt())

    def test_unopened_camera_cleanup(self):
        self.run_case(opened=False)

    def test_preview_does_not_wait_for_inference(self):
        cv2, factory, future = MagicMock(), MagicMock(), MagicMock()
        frame = MagicMock()
        cv2.VideoCapture.return_value.read.return_value = (True, frame)
        cv2.waitKey.side_effect = [-1, -1, ord("q")]
        future.done.return_value = False
        with patch.object(live, "ThreadPoolExecutor") as pool, \
                patch.object(live, "draw_overlay", side_effect=lambda cv, frame, *a: frame):
            pool.return_value.submit.return_value = future
            live.run_camera(live.parse_args([]), cv2, factory)
            pool.return_value.submit.assert_called_once()
        self.assertEqual(cv2.imshow.call_count, 3)
        future.result.assert_not_called()
        factory.assert_called_once()

    def test_keeps_latest_result_between_passes(self):
        cv2, factory, future = MagicMock(), MagicMock(), MagicMock()
        frame = MagicMock()
        cv2.VideoCapture.return_value.read.return_value = (True, frame)
        cv2.waitKey.side_effect = [-1, -1, ord("q")]
        future.done.return_value = True
        latest = live.summarize_result(result(["Contaminated"], [0.91]))
        future.result.return_value = latest
        with patch.object(live, "ThreadPoolExecutor") as pool, \
                patch.object(live.time, "monotonic", return_value=10.0), \
                patch.object(live, "draw_overlay", return_value=frame) as overlay:
            pool.return_value.submit.return_value = future
            live.run_camera(live.parse_args([]), cv2, factory)
            pool.return_value.submit.assert_called_once()
        self.assertEqual(overlay.call_args_list[0].args[2]["severity"], "GREY")
        self.assertIs(overlay.call_args_list[1].args[2], latest)
        self.assertIs(overlay.call_args_list[2].args[2], latest)


if __name__ == "__main__":
    unittest.main()
