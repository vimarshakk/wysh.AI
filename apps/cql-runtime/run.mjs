import cql from "cql-execution";
import cqlfhir from "cql-exec-fhir";

export async function executeElm({ elm, bundle }) {
  const library = new cql.Library(elm);
  const executor = new cql.Executor(library);
  const patientSource = cqlfhir.PatientSource.FHIRv401({ requireProfileTagging: false });
  patientSource.loadBundles([bundle]);
  const result = await executor.exec(patientSource);
  return result;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { elm, bundle } = JSON.parse(process.argv[2]);
  const result = await executeElm({ elm, bundle });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}
