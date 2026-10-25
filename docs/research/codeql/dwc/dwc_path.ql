/**
 * @name DWC task args to path sink
 * @description Traces DWC task/args/path parameters into file path sinks.
 * @kind path-problem
 * @problem.severity error
 * @id dwc/path-injection-task-input
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.security.dataflow.PathInjectionCustomizations
import semmle.python.security.dataflow.PathInjectionQuery
import PathInjectionFlow::PathGraph

class DwcPathSource extends PathInjection::Source instanceof DataFlow::ParameterNode {
  DwcPathSource() {
    exists(Function f, int i |
      f.getName() in ["_do_action", "execute_user_task", "_execute_user_task_impl"] and
      f.getArg(i).getName() in ["args", "task", "path", "prompt"] and
      this.getParameter() = f.getArg(i)
    )
  }
}

from PathInjectionFlow::PathNode source, PathInjectionFlow::PathNode sink
where PathInjectionFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "DWC task/args/path value reaches a file path sink.",
  sink.getNode().getLocation().toString()
