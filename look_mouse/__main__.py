import argparse

from .app import App
from .config import DEFAULT_PATH, Config
from .hid import FakeLink, HidLink, LockKeyListener
from .server import serve
from .tracker import SimTracker, Tracker


def main():
    ap = argparse.ArgumentParser(prog="look_mouse", description="Jump the mouse cursor to where you look.")
    ap.add_argument("--simulate", action="store_true",
                    help="no camera and no USB output; steer a pretend head from the web page")
    ap.add_argument("--config", default=DEFAULT_PATH)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    config = Config(args.config)
    tracker = SimTracker() if args.simulate else Tracker(config)
    link = FakeLink() if args.simulate else HidLink()
    app = App(config, tracker, link)

    tracker.start()
    LockKeyListener(link, config, app.jump).start()

    pin = config.data["trigger"]["gpio_pin"]
    if pin is not None and not args.simulate:
        try:
            from gpiozero import Button
            button = Button(int(pin))
            button.when_pressed = app.jump
        except Exception as e:
            print(f"GPIO button on pin {pin} unavailable: {e}")

    print(f"look-mouse interface on http://{args.host}:{args.port}" + ("  (simulation)" if args.simulate else ""))
    serve(app, args.host, args.port)


if __name__ == "__main__":
    main()
