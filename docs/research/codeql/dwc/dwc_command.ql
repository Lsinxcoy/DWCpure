/**
 * @name DWC task input to command execution
 * @description Traces DWC task/args parameters into command execution sinks.
 * @kind path-problem
 * @problem.severity error
 * @id dwc/command-injection-task-input
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.security.dataflow.CommandInjectionCustomizations
import semmle.python.security.dataflow.CommandInjectionQuery
import CommandInjectionFlow::PathGraph

class DwcTaskSource extends CommandInjection::Source instanceof DataFlow::ParameterNode {
  DwcTaskSource() {
    exists(Function f, int i |
      f.getName() in [
        "execute_user_task", "_execute_user_task_impl", "_do_action",
        "run_user_task", "run_command"
      ] and
      f.getArg(i).getName() in ["task", "args", "prompt", "cmd"] and
      this.getParameter() = f.getArg(i)
    )
  }
}

from CommandInjectionFlow::PathNode source, CommandInjectionFlow::PathNode sink
where CommandInjectionFlow::flowPath(source, sink)
select sink.getNode().getLocation(), source, sink,
  "DWC task/args value reaches a command execution sink."
