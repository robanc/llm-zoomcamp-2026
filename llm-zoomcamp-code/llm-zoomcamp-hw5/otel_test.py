from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

provider = TracerProvider()
provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("llm-zoomcamp")

from starter import rag


query = "How does the agentic loop keep calling the model until it stops?"

with tracer.start_as_current_span("rag") as span:
    span.set_attribute("query", query)

    answer = rag.rag(query)

    span.set_attribute("answer", answer)

print("\nANSWER:")
print(answer)