# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import logging
import time
import threading
import signal
import subprocess
from typing import Dict, Any, Optional, Callable
from collections import defaultdict


# Log
# - Updated `_handle_json_message` to parse Gemini output
# - Removed tool and cost limit enforcement
# - Removed `ProcessStreamReader`
# - Removed cost tracking code
# - Removed tool use heuristics
# - Removed ID format tracking
# - Removed JSON buffering logic
# - Removed `stop_callbacks` handling


class RealTimeStreamMonitor:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self.tool_calls = defaultdict(int)
        self.total_calls = 0
        
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
        self.process = None
    
    def monitor_process(self, process: subprocess.Popen) -> None:
        self.process = process
    
    def _process_output_line(self, line: str) -> None:
        try:
            cleaned_line = line.strip()
            if not cleaned_line:
                return

            if cleaned_line.startswith('{') and cleaned_line.endswith('}'):
                try:
                    data = json.loads(cleaned_line)
                    self._handle_json_message(data)
                    return
                except json.JSONDecodeError:
                    pass
                
        except Exception as e:
            pass

    def _try_parse_direct_json(self, json_str: str) -> bool:

        try:
            data = json.loads(json_str)
            self._handle_json_message(data)
            
            return True
        except json.JSONDecodeError:
            return False

    
    def _handle_json_message(self, data: Dict[str, Any]) -> None:

        message_type = data.get('type', '')
        
        if message_type == 'tool_use':
            tool_name = data.get('tool_name', '')
            tool_id = data.get('tool_id', '')
            
            if tool_name:
                self._handle_tool_call(tool_name, tool_id)
                
            return
                
        # Gemini does not produce stats in real-time. This is the last message.
        if message_type == 'result':
            stats = data.get('stats', {})
            self.total_input_tokens = stats.get('input_tokens', 0)
            self.total_output_tokens = stats.get('output_tokens', 0)
            return

    
    def _handle_tool_call(self, tool_name: str, tool_id: str = "") -> None:
        self.tool_calls[tool_name] += 1
        self.total_calls += 1
                
    
    def _handle_usage_data(self, usage: Dict[str, Any], model: str) -> None: 
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        
        if input_tokens > 0 or output_tokens > 0:     
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

    
    def analyze_completed_output(self, output_text: str) -> Dict[str, Any]:
        self.tool_calls.clear()
        self.total_calls = 0
        
        lines = output_text.split('\n')
        processed_lines = 0
        
        for line in lines:
            if line.strip():
                self._process_output_line(line.strip())
                processed_lines += 1
        

        analysis_result = {
            'analysis_type': 'post_process',
            'processed_lines': processed_lines,
            'detected_tool_calls': self.total_calls,
            'tool_breakdown': dict(self.tool_calls),
            'cost_estimation': {
                'total_input_tokens': self.total_input_tokens,
                'total_output_tokens': self.total_output_tokens
            }
        }
        
        return analysis_result
    
    def get_statistics(self) -> Dict[str, Any]:

        return {
            'tool_calls': dict(self.tool_calls),
            'total_tool_calls': self.total_calls,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
        }


class EnhancedProcessStreamReader:

    
    def __init__(self, process: subprocess.Popen, monitor: RealTimeStreamMonitor, gemini_runner=None):
        self.process = process
        self.monitor = monitor
        self.gemini_runner = gemini_runner  
        self.logger = logging.getLogger(__name__)
        
    def read_with_monitoring(self, timeout: Optional[int] = None) -> str:
  
        start_time = time.time()
        output_lines = []
        output_chunk_buffer = []  
        last_log_update = time.time()
        
        try:
            while True:
                if timeout and (time.time() - start_time) > timeout:
                    raise subprocess.TimeoutExpired(self.process.args, timeout)
                

                return_code = self.process.poll()
                if return_code is not None:
                    break
                       
                if self.process.stdout:
                    try:
                        line = self.process.stdout.readline()
                        if line:

                            if isinstance(line, bytes):
                                decoded_line = line.decode('utf-8', errors='ignore')
                            else:
                                decoded_line = str(line)
                            output_lines.append(decoded_line)
                            output_chunk_buffer.append(decoded_line)
                            

                            self.monitor._process_output_line(decoded_line.strip())
                            
               
                            current_time = time.time()
                            if (current_time - last_log_update > 2.0 or 
                                len(output_chunk_buffer) >= 50):
                                self._update_real_time_log(output_chunk_buffer)
                                output_chunk_buffer.clear()
                                last_log_update = current_time                                                                                     
                    except Exception as e:
                        pass
                
                time.sleep(0.1)
                
        finally:

            try:
                if self.process.stdout:
                    remaining_output = self.process.stdout.read()
                    if remaining_output:

                        if isinstance(remaining_output, bytes):
                            decoded_output = remaining_output.decode('utf-8', errors='ignore')
                        else:
                            decoded_output = str(remaining_output)
                        output_lines.append(decoded_output)
                        output_chunk_buffer.append(decoded_output)
                        

                        for line in decoded_output.split('\n'):
                            if line.strip():
                                self.monitor._process_output_line(line.strip())
            except:
                pass
            

            if output_chunk_buffer and self.gemini_runner:
                self._update_real_time_log(output_chunk_buffer)
        
        return ''.join(output_lines)
    
    def _update_real_time_log(self, output_chunks: list) -> None:

        if not self.gemini_runner or not output_chunks:
            return
            
        try:

            combined_output = ''.join(output_chunks)
            
 
            self.gemini_runner._update_real_time_log(new_output_chunk=combined_output)
            
        except Exception as e:
            pass

    