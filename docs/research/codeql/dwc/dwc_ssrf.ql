/**
 * @name DWC task args to SSRF
 * @description Traces DWC task/args/url parameters into HTTP request sinks.
 * @kind path-problem
 * @problem.severity error
 * @id dwc/ssrf-task-input
 */

import python
import semmle.python.Concepts
import semmle.python.dataflow.new.DataFlow
import semmle.python.security.dataflow.ServerSideRequestForgeryCustomizations
import semmle.python.security.dataflow.ServerSideRequestForgeryQuery
import FullServerSideRequestForgeryFlow::PathGraph

class DwcUrlSource extends ServerSideRequestForgery::Source instanceof DataFlow::ParameterNode {
  DwcUrlSource() {
    exists(Function f, int i |
      f.getName() in ["_do_action", "execute_user_task", "_execute_user_task_impl"] and
      f.getArg(i).getName() in ["args", "task", "url", "prompt"] and
      this.getParameter() = f.getArg(i)
    )
  }
}

from
  FullServerSideRequestForgeryFlow::PathNode source,
  FullServerSideRequestForgeryFlow::PathNode sink,
  Http::Client::Request request
where
  request = sink.getNode().(ServerSideRequestForgery::Sink).getRequest() and
  FullServerSideRequestForgeryFlow::flowPath(source, sink)
select request.getLocation(), source, sink,
  "DWC task/args/url value reaches an HTTP request sink."
