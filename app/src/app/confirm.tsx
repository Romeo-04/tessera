import { Redirect } from "expo-router";
import { View } from "react-native";
import { Button, Note, Row, Screen, T } from "../components/ui";
import { useSession } from "../session/SessionProvider";
import { space } from "../theme";

export default function Confirm() {
  const { ambiguities, choices, decide, busy, notice, runAssess } = useSession();
  const ready = ambiguities.every((a) => a.raw_name in choices);
  if (ambiguities.length === 0) return <Redirect href="/" />;

  return (
    <Screen>
      <T>
        We could not tell {ambiguities.length === 1 ? "these" : "some of these"} apart. Rather than
        guess, we are asking.
      </T>

      {ambiguities.map((a) => {
        const decided = a.raw_name in choices;
        const pick = choices[a.raw_name];
        return (
          <View key={a.raw_name} style={{ marginBottom: space.s4 }}>
            <Note tone="warn">
              {`The label read ${a.raw_name}. `
                + (a.margin !== undefined
                  ? `The best two matches scored within ${a.margin.toFixed(3)} of each other — inside our margin.`
                  : "No match was clearly ahead.")}
            </Note>
            {a.options.map((o, i) => {
              const unavailable = a.precomputed !== undefined && !a.precomputed.includes(o.rxcui);
              return (
                <Row key={o.rxcui} icon={pick?.rxcui === o.rxcui ? "✓" : String(i + 1)}
                     title={o.display_name} selected={pick?.rxcui === o.rxcui} disabled={unavailable}
                     detail={`${o.rxcui} · match ${o.score.toFixed(3)}${unavailable ? " · demo has no precomputed answer" : ""}`}
                     onPress={() => decide(a.raw_name, o)} />
              );
            })}
            <Row icon={decided && pick === null ? "✓" : "–"} tone="out" selected={decided && pick === null}
                 title="Not sure — leave it out" detail="It will not be checked, and the result will say so"
                 onPress={() => decide(a.raw_name, null)} />
          </View>
        );
      })}

      <Note tone="lime">
        Until you choose, this medication carries no code — so nothing downstream can score it. An
        unanswered question is safer than a confident wrong answer.
      </Note>
      {notice && <Note tone="warn" role="alert">{notice}</Note>}
      <Button label={busy ? "Checking…" : "Check for interactions"} disabled={!ready || busy}
              onPress={() => void runAssess()} />
    </Screen>
  );
}
