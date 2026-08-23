import { useState } from "react";
import { SetupScreen } from "./components/SetupScreen";
import { RankingsScreen } from "./components/RankingsScreen";
import { CandidateDetailScreen } from "./components/CandidateDetailScreen";

type View =
  | { screen: "setup" }
  | { screen: "rankings"; jdId: number }
  | { screen: "detail"; jdId: number; evaluationId: number };

function App() {
  const [view, setView] = useState<View>({ screen: "setup" });

  if (view.screen === "setup") {
    return <SetupScreen onAnalysisComplete={(jdId) => setView({ screen: "rankings", jdId })} />;
  }

  if (view.screen === "rankings") {
    return (
      <RankingsScreen
        jdId={view.jdId}
        onSelectEvaluation={(evaluationId) => setView({ screen: "detail", jdId: view.jdId, evaluationId })}
        onBack={() => setView({ screen: "setup" })}
      />
    );
  }

  return (
    <CandidateDetailScreen
      evaluationId={view.evaluationId}
      onBack={() => setView({ screen: "rankings", jdId: view.jdId })}
    />
  );
}

export default App;
