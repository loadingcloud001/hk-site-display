import { Component, type ReactNode } from "react";

type Props = { resetKey: string; layout?: string; children: ReactNode };
type State = { failed: boolean };

// If the screen cannot be drawn (unexpected data, a bug), show a plain notice instead of a blank page, and try
// again with the next snapshot. An unattended gate screen must never stay frozen or empty.
export class Guard extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("screen failed to render", error);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.failed && prev.resetKey !== this.props.resetKey) this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="stage" data-tone="idle" data-layout={this.props.layout}>
        <div className="boot">畫面出錯 — 請以我的天文台為準</div>
      </div>
    );
  }
}
