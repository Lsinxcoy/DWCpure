/**
 * @name DWC model code to exec
 * @description Traces candidate/model source parameters into exec sinks.
 * @kind path-problem
 * @problem.severity error
 * @id dwc/code-injection-model-source
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.security.dataflow.CodeInjectionCustomizations
import semmle.python.security.dataflow.CodeInjectionQuery
import CodeInjectionFlow::PathGraph

class DwcCodeSource extends CodeInjection::Source instanceof DataFlow::ParameterNode {
  DwcCodeSource() {
    exists(Function f, int i |
      f.getName() in ["__init__", "_baseline_reproduces", "from_task_result",
                      "execute_task", "run_code_observed"] and
      f.getArg(i).getName() in ["source", "src", "body", "implementation", "code"] and
      this.getParameter() = f.getArg(i)
    )
  }
}

from CodeInjectionFlow::PathNode source, CodeInjectionFlow::PathNode sink
where CodeInjectionFlow::flowPath(source, sink)
select sink.getNode().getLocation(), source, sink,
  "DWC model/candidate source reaches an exec sink."
