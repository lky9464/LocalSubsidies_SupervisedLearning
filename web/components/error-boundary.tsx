"use client";

import { Component, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

type Props = { children: ReactNode; label?: string };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <Alert variant="destructive" className="m-4">
          <p className="font-medium">
            {this.props.label || "화면"} 오류: {this.state.error.message}
          </p>
          <Button
            className="mt-3"
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
          >
            새로고침
          </Button>
        </Alert>
      );
    }
    return this.props.children;
  }
}
