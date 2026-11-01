import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { executeElm } from "../run.mjs";

test("pinned CQF runtime executes the synthetic FHIR R4 ELM fixture", async () => {
  const elm = JSON.parse(await readFile(new URL("../../../disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json", import.meta.url)));
  const bundle = {
    resourceType: "Bundle",
    type: "collection",
    meta: { tag: [{ code: "synthetic" }] },
    entry: [{ resource: { resourceType: "Patient", id: "synthetic-runtime-patient" } }, { resource: { resourceType: "Observation", id: "runtime-glucose-1", code: { coding: [{ system: "http://loinc.org", code: "2339-0" }] }, valueQuantity: { value: 65, unit: "mg/dL" }, effectiveDateTime: "2026-10-01T00:00:00Z" } }],
  };
  const result = await executeElm({ elm, bundle });
  assert.equal(result.patientResults["synthetic-runtime-patient"].HasGlucoseObservation, true);
});

test("pinned CQF runtime follows FHIR retrieve semantics for missing observations", async () => {
  const elm = JSON.parse(await readFile(new URL("../../../disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json", import.meta.url)));
  const bundle = { resourceType: "Bundle", type: "collection", meta: { tag: [{ code: "synthetic" }] }, entry: [{ resource: { resourceType: "Patient", id: "synthetic-empty-patient" } }] };
  const result = await executeElm({ elm, bundle });
  assert.equal(result.patientResults["synthetic-empty-patient"].HasGlucoseObservation, false);
});
