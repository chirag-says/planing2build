# OR-Tools feasibility spike (AI_DESIGN_ENGINE_CHECKPOINT_1 section N). Throwaway: built on top of
# the current API image, never used by the application. The API's pyproject.toml and uv.lock are
# not changed; ortools is installed into this image's virtualenv only, so its resolution is checked
# against exactly the packages the API ships with.
#
#   docker build -t p2b-api:cp1-baseline apps/api
#   docker build -t p2b-api:cp1-ortools tools/spikes/ortools_feasibility
ARG BASE=p2b-api:cp1-baseline
FROM ${BASE}
USER root
RUN uv pip install --no-cache --python /app/.venv/bin/python "ortools==9.15.6755" \
    && uv pip check --python /app/.venv/bin/python
COPY bench.py /spike/bench.py
USER app
CMD ["python", "/spike/bench.py", "--runs", "20"]
