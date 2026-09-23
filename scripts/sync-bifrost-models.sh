#!/usr/bin/env bash
# Usage: sync-bifrost-models.sh [source] [destination]
# Defaults: $OPENCODE_CONFIG or ~/.config/opencode/opencode.json ->
#           $PI_MODELS_CONFIG or ~/.pi/agent/models.json

set -euo pipefail

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

command -v jq >/dev/null 2>&1 || die "jq is required"

if (( $# > 2 )); then
  die "usage: $0 [source] [destination]"
fi

source_file=${1:-${OPENCODE_CONFIG:-$HOME/.config/opencode/opencode.json}}
destination_file=${2:-${PI_MODELS_CONFIG:-$HOME/.pi/agent/models.json}}

if [[ -L "$destination_file" ]]; then
  die "destination is a symlink: $destination_file"
fi

[[ -f "$source_file" ]] || die "source not found: $source_file"

if ! jq -s -e '
  if length != 1 then false
  else .[0]
    | type == "object"
    and ((has("provider") | not) or (.provider | type == "object"))
    and all((.provider // {})[]; type == "object" and ((.models // {}) | type == "object"))
  end
' "$source_file" >/dev/null 2>&1; then
  die "source is missing or malformed: $source_file"
fi

if [[ -e "$destination_file" || -L "$destination_file" ]]; then
  [[ -f "$destination_file" ]] || die "destination is not a file: $destination_file"
  if ! jq -s -e '
    if length != 1 then false
    else .[0]
      | type == "object"
      and ((has("providers") | not) or (.providers | type == "object"))
      and all((.providers // {})[]; type == "object")
    end
  ' "$destination_file" >/dev/null 2>&1; then
    die "destination is missing or malformed: $destination_file"
  fi
fi

destination_dir=${destination_file%/*}
[[ "$destination_dir" == "$destination_file" ]] && destination_dir=.
mkdir -p "$destination_dir" || die "cannot create destination directory: $destination_dir"

tmp_file=$(mktemp "$destination_dir/.models.json.tmp.XXXXXX") || die "cannot create temporary file"
cleanup() {
  if [[ -n "${tmp_file:-}" && -e "$tmp_file" ]]; then
    rm -f "$tmp_file"
  fi
}
trap cleanup EXIT

jq_filter=$(cat <<'JQ'
def provider_name:
  if . == "bf" then "bifrost"
  elif . == "bf-a" then "bifrost-anthropic"
  elif . == "bf-g" then "bifrost-google"
  elif . == "bf-o" then "bifrost-openai"
  else .
  end;

def provider_api($key; $provider):
  (($provider.npm // "") | ascii_downcase) as $npm
  | if $key == "bf-a" or ($npm | test("anthropic")) then "anthropic-messages"
  elif $key == "bf-g" or ($npm | test("google|genai")) then "google-generative-ai"
  elif $key == "bf" or $key == "bf-o" or ($npm | test("openai")) then "openai-completions"
  else null
  end;

def supported_inputs:
  map(select(. == "text" or . == "image"))
  | if length > 0 then . else ["text"] end;

def model_from_entry:
  . as $entry
  | $entry.value as $model
  | ($model.modalities // {}) as $modalities
  | ($model.cost // {}) as $cost
  | ($model.limit // {}) as $limit
  | {
      id: $entry.key,
      name: ($model.name // $entry.key),
      reasoning: (if ($model.reasoning | type) == "boolean" then $model.reasoning else false end),
      input: (
        if ($modalities | type) == "object" and (($modalities.input | type) == "array") then ($modalities.input | supported_inputs)
        else ["text"]
        end
      )
    }
  + (if ($cost | type) == "object" and ($cost | length) > 0 then
      {cost: {
        input: (if $cost | has("input") then $cost.input else 0 end),
        output: (if $cost | has("output") then $cost.output else 0 end),
        cacheRead: (if $cost | has("cache_read") then $cost.cache_read else 0 end),
        cacheWrite: (if $cost | has("cache_write") then $cost.cache_write else 0 end)
      }}
     else {} end)
  + (if ($limit | type) == "object" and (($limit | has("context")) and ($limit.context != null))
     then {contextWindow: $limit.context} else {} end)
   + (if ($limit | type) == "object" and (($limit | has("output")) and ($limit.output != null))
      then {maxTokens: $limit.output} else {} end)
  ;

reduce ((.[0].provider // {}) | to_entries[] | select(.key == "bf" or .key == "bf-a" or .key == "bf-g" or .key == "bf-o")) as $entry
  (.[1];
    ($entry.key | provider_name) as $target_name
    | $entry.value as $provider
    | ($provider.options // {}) as $options
    | (.providers // {}) as $providers
    | ($providers[$target_name] // {}) as $existing
    | ([($provider.models // {}) | to_entries[] | model_from_entry]) as $models
    | (provider_api($entry.key; $provider)) as $mapped_api
    | .providers = ($providers + {
        ($target_name): (
          {}
          + (if ($options | type) == "object" and (($options.baseURL | type) == "string") and (($options.baseURL | length) > 0)
             then {baseUrl: $options.baseURL}
             elif (($existing.baseUrl | type) == "string") and (($existing.baseUrl | length) > 0)
             then {baseUrl: $existing.baseUrl}
             else {} end)
           + {api: $mapped_api}
            + {apiKey: "$BIFROST_VIRTUAL_KEY"}
           + {models: $models}
         )
       })
   )
JQ
)

validation_filter=$(cat <<'JQ'
def provider_name:
  if . == "bf" then "bifrost"
  elif . == "bf-a" then "bifrost-anthropic"
  elif . == "bf-g" then "bifrost-google"
  elif . == "bf-o" then "bifrost-openai"
  else .
  end;

def valid_api:
  type == "string"
  and (. == "openai-completions"
    or . == "anthropic-messages"
    or . == "google-generative-ai");

def valid_number:
  type == "number" and isfinite;

def valid_positive_number:
  valid_number and . > 0;

def valid_cost:
  type == "object"
  and (.input | valid_number)
  and (.output | valid_number)
  and (.cacheRead | valid_number)
  and (.cacheWrite | valid_number);

def valid_model:
  type == "object"
  and (.id | type == "string" and length > 0)
  and (.name | type == "string" and length > 0)
  and (.reasoning | type == "boolean")
  and (.input | (type == "array" and length > 0 and all(.[]; . == "text" or . == "image")))
  and ((has("contextWindow") | not) or (.contextWindow | valid_positive_number))
  and ((has("maxTokens") | not) or (.maxTokens | valid_positive_number))
  and ((has("cost") | not) or (.cost | valid_cost));

def valid_provider:
  type == "object"
  and (.baseUrl | type == "string" and length > 0)
  and (.api | valid_api)
  and (.apiKey == "$BIFROST_VIRTUAL_KEY")
  and (.models | (type == "array" and all(.[]; valid_model)));

.[0] as $source
| .[1] as $generated
| (($source.provider // {})
   | to_entries
   | map(select(.key == "bf" or .key == "bf-a" or .key == "bf-g" or .key == "bf-o")
         | (.key | provider_name))) as $synced_provider_names
| ($generated | type == "object" and (.providers | type == "object"))
  and ($synced_provider_names | all(.[]; ($generated.providers[.] | valid_provider)))
JQ
)

if [[ -e "$destination_file" || -L "$destination_file" ]]; then
  if ! jq -s "$jq_filter" "$source_file" "$destination_file" >"$tmp_file"; then
    die "failed to sync provider models"
  fi
else
  if ! jq -s "$jq_filter" "$source_file" <(printf '{}\n') >"$tmp_file"; then
    die "failed to sync provider models"
  fi
fi

if ! jq -s -e "$validation_filter" "$source_file" "$tmp_file" >/dev/null 2>&1; then
  die "generated synced providers or models are malformed"
fi

provider_count=$(jq '.providers | length' "$tmp_file") || die "failed to count synced providers"
model_count=$(jq '[.providers[]?.models[]?] | length' "$tmp_file") || die "failed to count synced models"
mv "$tmp_file" "$destination_file" || die "failed to replace destination"
tmp_file=

printf 'synced %s -> %s (%s providers, %s models)\n' \
  "$source_file" "$destination_file" "$provider_count" "$model_count"
