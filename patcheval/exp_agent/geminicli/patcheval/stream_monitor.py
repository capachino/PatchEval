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


class RealTimeStreamMonitor:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self.tool_calls = defaultdict(int)
        self.total_calls = 0
        
        self.id_format_stats = defaultdict(int)
        
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
        self.should_stop = False
        self.process = None
        self.stop_callbacks = []
        
        self._monitor_thread = None
        self._stop_event = threading.Event()
        
        self._json_buffer = ""
        self._in_json_block = False
        
    def add_stop_callback(self, callback: Callable[[str], None]) -> None:
        self.stop_callbacks.append(callback)
        
    def _notify_stop(self, reason: str) -> None:
        for callback in self.stop_callbacks:
            try:
                callback(reason)
            except Exception as e:
                pass
    
    def monitor_process(self, process: subprocess.Popen) -> None:
        self.process = process
        
    def _monitor_output_stream(self, process: subprocess.Popen) -> None:
        try:
            buffer = ""
            while process.poll() is None and not self._stop_event.is_set():
                if process.stdout and process.stdout.readable():
                    try:
                        data = process.stdout.read(1024)
                        if data:
       
                            if isinstance(data, bytes):
                                decoded_data = data.decode('utf-8', errors='ignore')
                            else:
                                decoded_data = str(data)
                            buffer += decoded_data
                            
        
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                if line.strip():
                                    self._process_output_line(line.strip())
                                    
      
                                    if self.should_stop:
                                        self._force_stop_process(process)
                                        return
                    except Exception as read_error:
                        pass
                        
                time.sleep(0.1)  
                
        except Exception as e:
            self.logger.error(f"{e}")
        finally:
            if buffer.strip():
                self._process_output_line(buffer.strip())
    
    def _process_output_line(self, line: str) -> None:
        try:
            cleaned_line = line.strip()
            if not cleaned_line:
                return
            
            self._process_json_buffer(cleaned_line)

            if cleaned_line.startswith('{') and cleaned_line.endswith('}'):
                try:
                    data = json.loads(cleaned_line)
                    self._handle_json_message(data)
                    return
                except json.JSONDecodeError:
                    pass
                
        except Exception as e:
            pass
    
    def _process_json_buffer(self, line: str) -> None:
        try:
    
            json_starts = ['{"type":"assistant"', '{"type":"user"', '{"type":"system"']
            
            for start_marker in json_starts:

                start_pos = line.find(start_marker)
                if start_pos != -1:
    
                    if self._json_buffer:
                        self._try_parse_buffered_json()
                    
           
                    potential_json = line[start_pos:]
                    
           
                    if potential_json.count('{') > 0 and potential_json.endswith('}'):
      
                        if self._try_parse_direct_json(potential_json):
                            return
                    

                    self._json_buffer = potential_json
                    self._in_json_block = True
                    return
            

            if self._in_json_block:
                self._json_buffer += line
                self._try_parse_buffered_json()
                
        except Exception as e:
            pass
    
    def _try_parse_direct_json(self, json_str: str) -> bool:

        try:
            data = json.loads(json_str)
            self._handle_json_message(data)
            
            return True
        except json.JSONDecodeError:
            return False
    
    def _try_parse_buffered_json(self) -> None:

        try:
            if not self._json_buffer:
                return
            

            data = json.loads(self._json_buffer)
            self._handle_json_message(data)
            
            

            self._json_buffer = ""
            self._in_json_block = False
            
        except json.JSONDecodeError:
      
            if len(self._json_buffer) > 50000:  
                
                self._json_buffer = ""
                self._in_json_block = False
        except Exception as e:
            pass

    
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

        id_format = self._detect_tool_id_format(tool_id)
        self.id_format_stats[id_format] += 1
    
        self.tool_calls[tool_name] += 1
        self.total_calls += 1
                
    
    def _detect_tool_id_format(self, tool_id: str) -> str:

        if not tool_id:
            return "unknown"
        elif tool_id.startswith("toolu_"):
            return "anthropic_standard"  # toolu_vrtx_01RBkp5F8vJdHc79K72WWxrY
        elif tool_id.startswith("call_") and "_" in tool_id[5:]:
            return "proxy_format"  # call_0_0ec5554d-b2d4-47b4-93c4-a3925153e469
        elif "_" in tool_id and tool_id.split("_")[-1].isdigit():
            return "simplified"  # TodoWrite_0, Bash_3
        else:
            return "custom"
    
    def _handle_usage_data(self, usage: Dict[str, Any], model: str) -> None:
 
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        
        if input_tokens > 0 or output_tokens > 0:     
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            
    
    def _force_stop_process(self, process: subprocess.Popen) -> None:

        
        try:

            if process.poll() is None:
                process.terminate()
                

                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:

                    process.kill()
                    process.wait()
                    
        except Exception as e:
                pass
    def stop_monitoring(self) -> None:
 
        pass
    
    def analyze_completed_output(self, output_text: str) -> Dict[str, Any]:

        

        self.tool_calls.clear()
        self.total_calls = 0
        self.id_format_stats.clear()
        
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
            'id_format_distribution': dict(self.id_format_stats),
            'cost_estimation': {
                'total_input_tokens': self.total_input_tokens,
                'total_output_tokens': self.total_output_tokens
            }
        }
        
        if self.tool_calls:
            tools_summary = ', '.join(f"{tool}:{count}" for tool, count in self.tool_calls.items())
        
        if self.id_format_stats:
            format_summary = ', '.join(f"{fmt}:{count}" for fmt, count in self.id_format_stats.items())
        
        return analysis_result
    
    def get_statistics(self) -> Dict[str, Any]:

        return {
            'tool_calls': dict(self.tool_calls),
            'total_tool_calls': self.total_calls,
            'id_format_stats': dict(self.id_format_stats),  
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
        }


class EnhancedProcessStreamReader:

    
    def __init__(self, process: subprocess.Popen, monitor: RealTimeStreamMonitor, claude_runner=None):
        self.process = process
        self.monitor = monitor
        self.claude_runner = claude_runner  
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
                
       
                if self.monitor.should_stop:
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
                            
                         
                            if self.monitor.should_stop:
                                break
                                
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
            

            if output_chunk_buffer and self.claude_runner:
                self._update_real_time_log(output_chunk_buffer)
        
        return ''.join(output_lines)
    
    def _update_real_time_log(self, output_chunks: list) -> None:

        if not self.claude_runner or not output_chunks:
            return
            
        try:

            combined_output = ''.join(output_chunks)
            
 
            self.claude_runner._update_real_time_log(new_output_chunk=combined_output)
            
        except Exception as e:
            pass

    