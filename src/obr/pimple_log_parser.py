from glob import glob
import numpy as np
import re
import logging
import gzip
import os

logger = logging.getLogger("foam-parser")

class LogParser:
    def __init__(
        self,
        log_file_path: str,
        lin_tol: bool = False,
        n_cells: float = None,
        n_cells_search_dir : str = None,
        t_skip: float = 0.0,
        write_interval: int = None,
        write_interval_search_dir : str = None,
    ):
        if not log_file_path:
            raise ValueError("At least one log file must be provided.")

        self.log_file_path = log_file_path 
        self.lin_tol = lin_tol
        self.n_cells = n_cells
        self.n_cells_search_dir = n_cells_search_dir
        self.t_skip = t_skip
        self.write_interval = write_interval
        self.write_interval_search_dir = write_interval_search_dir
        self.log_as_bigstring = self.get_file_as_str()

    def run_parser(self):
        if self.n_cells == None: 
            self.n_cells = self.get_n_cells_from_file()
        
        if self.write_interval == None:
            self.write_interval = self.get_write_interval_from_file()

        output = self.get_all_info()
        return output
    
    @staticmethod
    def is_pimple_log(log_path) -> bool:
        """PIMPLE prints 'PIMPLE: iteration N' each outer loop; PISO/SIMPLE don't."""
        with open(log_path, "r", errors="ignore") as f:
            return any("PIMPLE: iteration" in line for line in f)
        
    def get_schemes_from_log(self):
        def parse_fvschemes(content):
            """Parse OpenFOAM fvSchemes dictionary into nested Python dict"""
            
            # Remove comments and headers
            content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            
            def extract_key(text):
                """Extract a key, handling nested parentheses"""
                i = 0
                paren_count = 0
                
                while i < len(text):
                    char = text[i]
                    
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                    elif char in ('{', ';', '\n') and paren_count == 0:
                        # Found the end of the key
                        return text[:i].strip(), text[i:]
                    elif char.isspace() and paren_count == 0:
                        # Check if this is the separator between key and value
                        return text[:i].strip(), text[i:]
                    
                    i += 1
                
                return text.strip(), ""
            
            def parse_block(text):
                """Recursively parse a block of text enclosed in braces"""
                result = {}
                text = text.strip()
                
                i = 0
                while i < len(text):
                    # Skip whitespace
                    while i < len(text) and text[i].isspace():
                        i += 1
                    
                    if i >= len(text):
                        break
                    
                    # Extract the key
                    key, remainder = extract_key(text[i:])
                    if not key:
                        i += 1
                        continue
                    
                    i += len(text[i:]) - len(remainder)
                    
                    # Skip whitespace
                    while i < len(text) and text[i].isspace():
                        i += 1
                    
                    if i >= len(text):
                        break
                    
                    # Check if next character is a brace (nested block)
                    if text[i] == '{':
                        # Find matching closing brace
                        brace_count = 1
                        start = i + 1
                        i += 1
                        while i < len(text) and brace_count > 0:
                            if text[i] == '{':
                                brace_count += 1
                            elif text[i] == '}':
                                brace_count -= 1
                            i += 1
                        
                        # Recursively parse the nested block
                        block_content = text[start:i-1]
                        result[key] = parse_block(block_content)
                    
                    # Check if it's a semicolon-terminated value
                    elif text[i] != ';':
                        # Find the semicolon
                        semi_pos = text.find(';', i)
                        if semi_pos != -1:
                            value = text[i:semi_pos].strip()
                            result[key] = value
                            i = semi_pos + 1
                        else:
                            i += 1
                    else:
                        # Just a key with no value (edge case)
                        result[key] = None
                        i += 1
                
                return result
            
            # Find the main dictionary (fvSchemes { ... })
            main_match = re.search(r'fvSchemes\s*\{', content)
            if not main_match:
                return {}
            
            # Find matching closing brace
            start = main_match.end() - 1
            brace_count = 1
            i = start + 1
            while i < len(content) and brace_count > 0:
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                i += 1
            
            main_block = content[start+1:i-1]
            return parse_block(main_block)
        
        def get_all_variables_global(d, exclude_default=True):
            """Get all variables/keys globally across all sections as a flat list"""
            all_vars = set()
            
            for section, content in d.items():
                if isinstance(content, dict):
                    for key in content.keys():
                        if not (exclude_default and key == 'default'):
                            all_vars.add(key.replace("phi,", ""))
            
            return sorted(list(all_vars))
        

        def simplify_keys(d):
            """Convert keys like 'div(phi,U)' to just 'phi,U'"""
            result = {}
            for key, value in d.items():
                if isinstance(value, dict):
                    result[key] = simplify_keys(value)
                else:
                    # Extract content between outermost parentheses
                    # Find first ( and last )
                    first_paren = key.find('(')
                    last_paren = key.rfind(')')
                    if first_paren != -1 and last_paren != -1 and first_paren < last_paren:
                        simple_key = key[first_paren+1:last_paren]
                        # Strip outer parentheses if they exist
                        if simple_key.startswith('(') and simple_key.endswith(')'):
                            simple_key = simple_key[1:-1]
                    else:
                        simple_key = key
                    result[simple_key] = value
            return result


        parsed = parse_fvschemes(self.log_as_bigstring)

        entries = {}
        for i in get_all_variables_global(simplify_keys(parsed)):
            obj = {
                "ddt_schemes": simplify_keys(parsed).get("ddtSchemes", {}).get(i) or simplify_keys(parsed).get("ddtSchemes", {}).get(f"phi,{i}") or simplify_keys(parsed).get("ddtSchemes", {}).get("default") or None,
                "div_schemes": simplify_keys(parsed).get("divSchemes", {}).get(i) or simplify_keys(parsed).get("divSchemes", {}).get(f"phi,{i}") or simplify_keys(parsed).get("divSchemes", {}).get("default") or None,
                "laplacian_schemes": simplify_keys(parsed).get("laplacianSchemes", {}).get(i) or simplify_keys(parsed).get("laplacianSchemes", {}).get("default") or None,
                "sn_grad_schemes": simplify_keys(parsed).get("snGradSchemes", {}).get(i) or simplify_keys(parsed).get("snGradSchemes", {}).get(f"phi,{i}") or simplify_keys(parsed).get("snGradSchemes", {}).get("default") or None,
                "interpolation_schemes": simplify_keys(parsed).get("interpolationSchemes", {}).get(i) or simplify_keys(parsed).get("interpolationSchemes", {}).get(f"phi,{i}") or simplify_keys(parsed).get("interpolationSchemes", {}).get("default") or None,
                "thermophysical_properties": simplify_keys(parsed).get("thermophysical_properties", {}).get(i) or simplify_keys(parsed).get("thermophysical_properties", {}).get(f"phi,{i}") or simplify_keys(parsed).get("thermophysical_properties", {}).get("default") or None,
                "turbulence_model_type": simplify_keys(parsed).get("turbulence_model_type", {}).get(i) or simplify_keys(parsed).get("turbulence_model_type", {}).get(f"phi,{i}") or simplify_keys(parsed).get("turbulence_model_type", {}).get("default") or None,
                "turbulence_model_type_name": simplify_keys(parsed).get("turbulence_model_type_name", {}).get(i) or simplify_keys(parsed).get("turbulence_model_type_name", {}).get(f"phi,{i}") or simplify_keys(parsed).get("turbulence_model_type_name", {}).get("default") or None,
                "turbulence_model_les_delta": simplify_keys(parsed).get("turbulence_model_les_delta", {}).get(i) or simplify_keys(parsed).get("turbulence_model_les_delta", {}).get(f"phi,{i}") or simplify_keys(parsed).get("turbulence_model_les_delta", {}).get("default") or None,
                "turbulence_model_coefficients": simplify_keys(parsed).get("turbulence_model_coefficients", {}).get(i) or simplify_keys(parsed).get("turbulence_model_coefficients", {}).get(f"phi,{i}") or simplify_keys(parsed).get("turbulence_model_coefficients", {}).get("default") or None,
                "thermophysical_properties_eos": simplify_keys(parsed).get("thermophysical_properties_eos", {}).get(i) or simplify_keys(parsed).get("thermophysical_properties_eos", {}).get(f"phi,{i}") or simplify_keys(parsed).get("thermophysical_properties_eos", {}).get("default") or None,
                "thermophysical_properties_energy": simplify_keys(parsed).get("thermophysical_properties_energy", {}).get(i) or simplify_keys(parsed).get("thermophysical_properties_energy", {}).get(f"phi,{i}") or simplify_keys(parsed).get("thermophysical_properties_energy", {}).get("default") or None,
                "thermophysical_properties_transport": simplify_keys(parsed).get("thermophysical_properties_transport", {}).get(i) or simplify_keys(parsed).get("thermophysical_properties_transport", {}).get(f"phi,{i}") or simplify_keys(parsed).get("thermophysical_properties_transport", {}).get("default") or None
            }
            entries[i] = obj

        return entries
    def get_write_interval_from_log(self) -> int:
        if self.log_as_bigstring is None: 
            raise ValueError("Log file not loaded. Please load the log file before trying to extract information from it.")
        
        match = re.search(r'writeInterval\s+(\d+)\s*;', self.log_as_bigstring)

        if match:
            number = int(match.group(1))
            return number        
        else:
            return None
    
    def get_n_cells_from_log(self) -> int:
        if self.log_as_bigstring is None: 
            raise ValueError("Log file not loaded. Please load the log file before trying to extract information from it.")
        match = re.search(r"Total number of cells\s*=\s*(\d+)", self.log_as_bigstring)

        if match:
            return int(match.group(1))
        else:
            return None

    def get_time_from_log(self) -> float:
        if self.log_as_bigstring is None: 
            raise ValueError("Log file not loaded. Please load the log file before trying to extract information from it.")
        match = re.search(r"Time\s*=\s*([\d.]+)", self.log_as_bigstring)

        if match:
            return float(match.group(1))
        else:
            return None

    def get_scheme_from_log(self) -> dict:
        if self.log_as_bigstring is None: 
            raise ValueError("Log file not loaded. Please load the log file before trying to extract information from it.")
        schemes = self.get_schemes_from_log()
        return schemes
    
    def get_all_info(self):
        known_residual_options=['Ux','Uy','Uz','p','k','omega','epsilon','nuTilda','ReThetat','gammaInt']

        n_cells_from_log = self.get_n_cells_from_log()
        if n_cells_from_log is not None:
            logger.info(f"Detected number of cells from log: {n_cells_from_log}")
            self.n_cells = n_cells_from_log
        
        if self.n_cells is None:
            logger.fatal("Could not determine number of cells from log. Please provide n_cells as an option to this script.")
            return None

        write_interval_from_log = self.get_write_interval_from_log()
        if write_interval_from_log is not None:
            logger.info(f"Detected write interval from log: {write_interval_from_log}")
            self.write_interval = write_interval_from_log
        
        if self.write_interval is None:
            logger.fatal("Could not determine write interval from log. Please provide write_interval as an option to this script.")
            return None
        
        t_skip_interval_from_log = self.get_time_from_log()
        if t_skip_interval_from_log is not None:
            logger.info(f"Detected time interval from log: {t_skip_interval_from_log}")
            self.t_skip = t_skip_interval_from_log

        if self.t_skip is None:
            logger.fatal("Could not determine time interval from log. Please provide t_skip as an option to this script.")
            return None
        
        
        # Get static parameters by searching the log as one big string
        available_residuals=[]
        all_resis_dict={}
        if self.lin_tol:
            all_final_resis_dict={}
        all_solvers_dict={}
        
        bigstring=self.log_as_bigstring
        lines = bigstring.split('\n')
        # Some general parameters
        nProc=int(re.search(r'\bnProcs :\s+([0-9]+)',bigstring).group(1))
        try:
            turbModel=re.search(r'turbulence model\s+(?!type)(\w+)',bigstring).group(1)
        except:
            turbModel="laminar"
        casename=re.search(r'Case.*\/(.*)',bigstring).group(1)
        OFversion=re.search(r'Version.*:\s+(\w+)',bigstring).group(1)
        host=re.search(r'Host.*:\s+(.*)',bigstring).group(1)
        date=re.search(r'Date.*:\s+(.*)',bigstring).group(1)
        time=re.search(r'Time.*:\s+(.*)',bigstring).group(1)
        # Always use user provided nCells via option to this script, if present
        nCells=self.n_cells
        # Detect used functionObjects if they are mentioned before the first time step
        fobjects_string=re.search(r'(?s)Starting time loop(.*?)Courant Number',bigstring).group(1)
        fobjects_found=re.findall(r'(?<=\n)(\w+)',fobjects_string)
        fobjects=[]
        for element in fobjects_found:
            cntr=fobjects_found.count(element)
            # Detect usage of upcco outputs as one function Object (By keyword "Using")
            if element=="Using":
                element="upcco"
            # Sum-up repeated usage of the same functionObject class and show as integer in report
            if not any(element in word for word in fobjects):
                fobjects.append("%ix %s" % (cntr,element))
        executable=list(filter(None,re.search(r'Exec.*:\s+(\w+)|.*\/(\w+)',bigstring).groups()))[0]
        # Add revision number to ucfdFOAM solvers
        revision=re.search(r'Revision.*:\s+(\d+)',bigstring)
        if revision:
            executable=executable + " Rev-" + revision.group(1)
        # Detect upcco outputs #2 TODO Repeated detection, but safer keyword remedy? (old upcco version)
        if re.search(r'\bupcco:init',bigstring):
            incl_upcco=True
        elif re.search(r'\bupcco(.*?): init time',bigstring): # (newest upcco version 1.4.0)
            incl_upcco=True
            upccoNewLog=True
        else:
            incl_upcco=False
            upccoNewLog=False

        # Check if which residuals are present in this particular log
        for resi in known_residual_options:
            matchstring=r'\b'+ resi + '.*?\='
            if re.search(matchstring,bigstring):
                available_residuals.append(resi)
                # Write used linear solvers into dictionary for all variables, write only one entry for vector quantities ending with x,y or z
                matchLinSolv=r'(\w+):  Solving for '+resi
                if resi.endswith('x') or resi.endswith('y') or resi.endswith('z'):
                    resi = resi[:-1]
                all_solvers_dict[resi]=re.search(matchLinSolv,bigstring).group(1)
        # Prepare dictionary for all found residuals
        for resi2 in available_residuals:
            all_resis_dict[resi2]=[]
            if self.lin_tol:
                all_final_resis_dict[resi2]=[]


        # Get dynamic parameters by searching the log line by line
        executionTime=[]
        clockTime=[]
        nPimpleList=[]
        upcco=[]
        upccoGB=[]
        upccoSolverTime=[]
        simTime=[]
        writeTime=[]
        menacalcTime=[]
        iters_p_list=[]
        nContiCalcs=0
        tmp_iters_p=0
        listen4write=False
        
        for line in lines:
            # Accumulate number of times continuity error is calculated in the first time step to determine number of inner loops
            if len(simTime)==1:
                tmp_conti=re.search(r'\btime step continuity',line)
                if tmp_conti:
                    nContiCalcs+=1
                
            # Detect PIMPLE Loop of current timestep
            npimple=re.search(r'\bPIMPLE: iteration\s+([0-9]+)',line)
            if npimple:
                tmp_nPimple=int(npimple.group(1))
            # Match number of linear solver iterations
            iters_p_loc=re.search(r'\bp, Init.*?Iterations\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)',line)
            if iters_p_loc:
                tmp_iters_p+=int(iters_p_loc.group(1))
            # Execution time
            newloop=re.search(r'\bExecutionTime =\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?).*\b([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)',line)
            if newloop:
                executionTime.append(float(newloop.group(1)))
                clockTime.append(float(newloop.group(3)))
                nPimpleList.append(tmp_nPimple)
                iters_p_list.append(tmp_iters_p)
                tmp_iters_p=0
            # Detected upcco update times
            if incl_upcco:
                if upccoNewLog:
                    t_upcco=re.search(r'Upcco\(.*\): commit time\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)+s, written data\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)+GB, \[solver time\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)+s\]',line)
                    if t_upcco:
                        upcco.append(float(t_upcco.group(1)))
                        upccoGB.append(float(t_upcco.group(3)))
                        upccoSolverTime.append(float(t_upcco.group(5)))
                else:
                    t_upcco=re.search(r'\bupcco:update time:\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)',line)
                    if t_upcco:
                        upcco.append(float(t_upcco.group(1)))
            # Simulation time 
            tmp_simTime=re.search(r'\bTime =\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)',line)
            if tmp_simTime:
                listen4write=True
                listen4meancalc=True
                simTime.append(float(tmp_simTime.group(1)))
            # Detected write times
            tmp_iswrite=re.search(r'(?<!fieldAverage )write',line)
            if tmp_iswrite and listen4write:
                listen4write=False
                writeTime.append(len(simTime))
            # Write residuals to dict
            for resi3 in available_residuals:
                matchstring2=r'\b'+ resi3 + ', Init.*?\=\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?).*?\=\s+([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)'            
                match=re.search(matchstring2,line)
                if match:
                    all_resis_dict[resi3].append(float(match.group(1)))
                    if self.lin_tol:
                        all_final_resis_dict[resi3].append(float(match.group(3)))
            # Search for meancalc runtime control execution
            tmp_isMeancalc=re.search(r'^Running meancalc',line)
            if tmp_isMeancalc and listen4meancalc:
                listen4meancalc=False
                menacalcTime.append(len(simTime))

        # Protect against interrupted logs
        minlength=len(executionTime)
        minlength_nOuterCorr=sum(nPimpleList[:minlength])
        # Calculate subiterations
        try:
            nSubIters=round(len(all_resis_dict['p'])/len(all_resis_dict['Ux'][:minlength_nOuterCorr]))
            logger.info(f"Determined number of sub-iterations: {nSubIters}")
        except Exception as e:
            logger.fatal('Could not determine number of sub-iterations. Possibly pressure p and/or velocity Ux residuals are missing in log.')
            return None
        minlength_p=nSubIters*minlength_nOuterCorr
        # simTime is extracted first, if log is interrupted it will be longer than the other arrays, thus shorten in to the minlength
        simTime=simTime[:minlength]
        #Save initial clockTime for later calculation of tinit
        clockTime_init=clockTime[0]
        nPimple_init=nPimpleList[0]
        tskip=self.t_skip
        # Cut off initial transient if desired
        if tskip > 0:
            len_old=len(simTime)
            mask_init_transient=np.array(simTime) > tskip
            simTime=np.array(simTime)[mask_init_transient].tolist()
            nThrowAway_t=len_old-len(simTime)
            logger.info(f"Number of time steps to throw away: {nThrowAway_t}")
            nThrowAway_normal=sum(nPimpleList[:nThrowAway_t])
            logger.info(f"Number of Pimple iterations to throw away: {nThrowAway_normal}")
            nThrowAway_p=nSubIters*nThrowAway_normal
            executionTime=np.array(executionTime)[mask_init_transient].tolist()
            clockTime=np.array(clockTime)[mask_init_transient].tolist()
            nPimpleList=np.array(nPimpleList)[mask_init_transient].tolist()
            iters_p_list=np.array(iters_p_list)[mask_init_transient].tolist()
            if incl_upcco:
                upcco=np.array(upcco)[mask_init_transient].tolist()
            for resi3 in available_residuals:
                if resi3 == "p":
                    all_resis_dict[resi3]=all_resis_dict[resi3][nThrowAway_p:]
                    if self.lin_tol:
                        all_final_resis_dict[resi3]=all_final_resis_dict[resi3][nThrowAway_p:]
                elif len(all_resis_dict[resi3]) < len(all_resis_dict['Ux'])-10:  # Handle variables that are only calculated on the last iteration
                    all_resis_dict[resi3]=all_resis_dict[resi3][nThrowAway_t:]
                    if self.lin_tol:
                        all_final_resis_dict[resi3]=all_final_resis_dict[resi3][nThrowAway_t:]
                else:
                    all_resis_dict[resi3]=all_resis_dict[resi3][nThrowAway_normal:]
                    if self.lin_tol:
                        all_final_resis_dict[resi3]=all_final_resis_dict[resi3][nThrowAway_normal:]
            # Recalculate if lengths and subiters so match shortended lists
            minlength=len(executionTime)
            minlength_nOuterCorr=sum(nPimpleList[:minlength])
            # Calculate subiterations
            try:
                nSubIters=round(len(all_resis_dict['p'])/len(all_resis_dict['Ux'][:minlength_nOuterCorr]))
            except Exception as e:
                logger.fatal('Could not determine number of sub-iterations. Possibly pressure p and/or velocity Ux residuals are missing in log.')
                return None
            minlength_p=nSubIters*minlength_nOuterCorr

        # Determine the timeStep to show in the plots (Three time steps before the last - this prevents from any plot error due to interupted logs)
        if len(simTime) <= 3:
            someTimeStep=simTime[0]
        else:
            someTimeStep=simTime[-4]
        showPimpleResidualsAtTime=someTimeStep

        # Determine timeStep size
        if len(simTime) == 1:
            timeStepSize=simTime[0]
        else:
            timeStepSize=simTime[-1]-simTime[-2]

        # Get ID of the determined timeStep
        idx=simTime.index(showPimpleResidualsAtTime)
        # Get start and end ID in velocity and pressure residuals
        idx_loop_start=sum(nPimpleList[:idx])
        idx_loop_start_p=sum([ele * nSubIters for ele in nPimpleList[:idx]])

        # Determine differences of execution and clock time
        tPerDt=np.diff(executionTime)
        tClockPerDt=np.diff(clockTime)
        # Subtract initial upcco time of present
        if incl_upcco:
            if upccoNewLog:
                tClockPerDt = np.array(upccoSolverTime[1:]) + np.array(upcco[:-1])
            tPerDt[0] -= upcco[0]
            tClockPerDt[0] -= upcco[0]

        # Throw first entry in the list of number of PIMPLE loops per dt away, since tPerDt values start from the second timeStep
        nOuterCorrs=nPimpleList[1:]
        # Calculate mean, standard dev and min/max of nPIMPLE loops
        nOuterCorrsMean=np.mean(nOuterCorrs)
        nOuterCorrsStd=np.std(nOuterCorrs)
        nOuterCorrsMax=max(nOuterCorrs)
        nOuterCorrsMin=min(nOuterCorrs)
        # Throw last entry in upcco away since it's logged after the last time step 
        overlength=len(tPerDt)-len(upcco)
        if overlength == -1:
            upcco_=upcco[:-1]
        else:
            upcco_=upcco

        # Allocate inner loops to nOC and nCorr (Determined from first time step)
        nCorrectors=int(nContiCalcs/nPimple_init)
        nonOrthoCorr=int((nSubIters-nCorrectors)/nCorrectors)

        # Handle different results of automatic write interval detection
        # Initialise boolean masks for writeTimes
        mask_fobjs = np.zeros(len(tPerDt),dtype=bool)
        mask_restart = np.zeros(len(tPerDt),dtype=bool)

        # If provided, use writeInterval passed as option to this script
        writeInterval=self.write_interval

        if not writeInterval:
            if writeTime:
                # Use detected writeInterval from log
                writeInterval=writeTime[0]
            else:
                raise ValueError("Could not determine writeInterval from log. Please provide writeInterval as an option to this script.")

        # Shift id of writeTimes if part of the data is skipped
        intervalStart=0
        if tskip > 0:
            intervalStart=nThrowAway_t % writeInterval
        # Get IDs of writeTimes and convert to mask array
        idx_write_fobjs=np.arange(writeInterval-intervalStart-1,len(tPerDt),writeInterval)
        #idx_write_restart=np.arange(writeInterval-intervalStart-1,len(tPerDt),writeInterval)
        idx_write_restart=np.arange(writeInterval-intervalStart-2,len(tPerDt),writeInterval)
        if len(tPerDt) == writeInterval-1:
            np.put(mask_restart,-1,np.ones(1,dtype=bool))
            logger.fatal('Could not determine OH of writing and excuting functionObjects. At least 2 writeIntervals are necessary!')
        else:
            np.put(mask_fobjs,idx_write_fobjs,np.ones(len(idx_write_fobjs),dtype=bool))
            np.put(mask_restart,idx_write_restart,np.ones(len(idx_write_restart),dtype=bool))

        # Handle OH of menacalc call and initialise boolean masks
        mask_meancalc = np.zeros(len(tPerDt),dtype=bool)
        if len(menacalcTime) > 0:
            mask_meancalc[[i-1 for i in menacalcTime]] = True

        # Handle OH o upcco write and initialise boolean masks
        mask_upcco = np.zeros(len(tPerDt),dtype=bool)
        mask_upccoOH = np.zeros(len(tPerDt),dtype=bool)
        if incl_upcco and upccoNewLog:
            mask_upccoOH = np.array(upccoGB[:-1])>0
            mask_upcco = np.array(upccoGB[1:])>0

        # Fuse the two write masks
        #mask_write=np.logical_or(mask_fobjs,mask_restart)
        mask_write=np.logical_or.reduce([mask_fobjs,mask_restart,mask_upccoOH])
        # Fuse the two write masks and the meancalc mask to distinguish raw timeSteps
        mask=np.logical_or.reduce([mask_fobjs,mask_restart,mask_upccoOH,mask_meancalc])
        mask_restartAlone=np.logical_and.reduce([mask_restart,~mask_fobjs,~mask_upccoOH,~mask_meancalc])
        mask_fobjsAlone=np.logical_and.reduce([~mask_restart,mask_fobjs,~mask_meancalc]) 
        mask_upccoAlone=np.logical_and.reduce([~mask_restart,~mask_fobjs,mask_upccoOH,~mask_meancalc])
        mask_meancalcAlone=np.logical_and.reduce([~mask_restart,~mask_fobjs,~mask_upccoOH,mask_meancalc])
        # Calculate difference between clock and execution time and allocate to their sources
        clockdiff=tClockPerDt-tPerDt
        # Set negative values to 0. The clocktime in the log is rounded to full integer seconds which can result negative values for clockdiff
        clockdiff[clockdiff<0]=0
        clockdiff_sum=sum(clockdiff)
        clockdiff_share_writes=sum(clockdiff[mask_write])
        clockdiff_share_restartWrites=sum(clockdiff[mask_restart])
        clockdiff_share_fObjWrites=sum(clockdiff[mask_fobjs])
        clockdiff_share_meancalc=sum(clockdiff[mask_meancalcAlone])
        clockdiff_share_dt=sum(clockdiff[~mask])
        clockdiff_perWrite=np.mean(clockdiff[mask_write])
        clockdiff_perRestartWrite=np.mean(clockdiff[mask_restartAlone])
        clockdiff_perfObjWrite=np.mean(clockdiff[mask_fobjs])
        clockdiff_perMeancalc=np.mean(clockdiff[mask_meancalcAlone]) if any(mask_meancalcAlone) else sum(clockdiff[mask_meancalc])
        clockdiff_perDt=np.mean(clockdiff[~mask])

        # Calculate normalised overhead time
        eff_clockdiff_perDt=np.divide(nProc*clockdiff[~mask],int(nCells)*np.array(np.array(nOuterCorrs)[~mask]))
        eff_clockdiff_mean=np.mean(eff_clockdiff_perDt)
        eff_clockdiff_std=np.std(eff_clockdiff_perDt)

        # Calculate normalised CPU time (Efficiency?) for raw timeSteps 
        #eff_base=np.divide(nProc*(tPerDt[~mask]+clockdiff[~mask]),int(nCells)*np.array(np.array(nOuterCorrs)[~mask]))
        #eff_base=np.divide(nProc*(tPerDt[~mask]),int(nCells)*np.array(np.array(nOuterCorrs)[~mask]))
        eff_base=np.divide(nProc*(tClockPerDt[~mask]),int(nCells)*np.array(np.array(nOuterCorrs)[~mask]))
        eff_base_mean=np.mean(eff_base)
        eff_base_std=np.std(eff_base)

        # Calculate mean for pressure iterations in lin. solver
        iters_p_mean=np.mean(iters_p_list)

        # Calculate mean values for tPerDt and upcco
        tPerDt_mean=np.mean(tPerDt[~mask])
        tinit=clockTime_init-tPerDt_mean
        tPerDt_std=np.std(tPerDt[~mask])
        if incl_upcco:
            if upccoNewLog:
                upcco_mean=np.mean(np.array(upcco[:-1])[mask_upccoOH])
            else:
                upcco_mean=np.mean(np.array(upcco_)[mask_fobjsAlone if any(mask_fobjsAlone) else mask_fobjs])
        else:
            upcco_mean=0.0

        # Calcualte linear solver tolerances
        if self.lin_tol:
            relTolDict={}
            absTolMeanDict={}
            absTolStdDict={}
            relTolMeanDict={}
            relTolStdDict={}
            absTolFinalMeanDict={}
            absTolFinalStdDict={}
            relTolFinalMeanDict={}
            relTolFinalStdDict={}
            #Calculate final iteration index
            finalIterIdx=np.cumsum(nPimpleList[:minlength])-1
            finalIterIdx_p=np.cumsum([ele * nSubIters for ele in nPimpleList[:minlength]])-1
            for element in all_resis_dict:
                relTolDict[element]=np.divide(np.array(all_final_resis_dict[element]),np.array(all_resis_dict[element]))
                if element=='p':
                    absTolFinalMeanDict[element]=np.mean(np.array(all_final_resis_dict[element])[finalIterIdx_p])
                    absTolFinalStdDict[element]=100*np.std(np.array(all_final_resis_dict[element])[finalIterIdx_p])/absTolFinalMeanDict[element]
                    absTolMeanDict[element]=np.mean(np.delete(np.array(all_final_resis_dict[element]),finalIterIdx_p))
                    absTolStdDict[element]=100*np.std(np.delete(np.array(all_final_resis_dict[element]),finalIterIdx_p))/absTolMeanDict[element]
                    relTolFinalMeanDict[element]=np.mean(relTolDict[element][finalIterIdx_p])
                    relTolFinalStdDict[element]=100*np.std(relTolDict[element][finalIterIdx_p])/relTolFinalMeanDict[element]
                    relTolMeanDict[element]=np.mean(np.delete(relTolDict[element],finalIterIdx_p))
                    relTolStdDict[element]=100*np.std(np.delete(relTolDict[element],finalIterIdx_p))/relTolMeanDict[element]
                elif len(all_final_resis_dict[element]) < len(all_final_resis_dict['Ux']):
                    absTolFinalMeanDict[element]=np.mean(all_final_resis_dict[element])
                    absTolFinalStdDict[element]=100*np.std(all_final_resis_dict[element])/absTolFinalMeanDict[element]
                    absTolMeanDict[element]=absTolFinalMeanDict[element]
                    absTolStdDict[element]=absTolFinalStdDict[element]
                    relTolFinalMeanDict[element]=np.mean(relTolDict[element])
                    relTolFinalStdDict[element]=100*np.std(relTolDict[element])/relTolFinalMeanDict[element]
                    relTolMeanDict[element]=relTolFinalMeanDict[element]
                    relTolStdDict[element]=relTolFinalStdDict[element]
                    finalIterIdx=np.ones(len(all_final_resis_dict[element]),dtype=bool)
                else:
                    absTolFinalMeanDict[element]=np.mean(np.array(all_final_resis_dict[element])[finalIterIdx])
                    absTolFinalStdDict[element]=100*np.std(np.array(all_final_resis_dict[element])[finalIterIdx])/absTolFinalMeanDict[element]
                    absTolMeanDict[element]=np.mean(np.delete(np.array(all_final_resis_dict[element]),finalIterIdx))
                    absTolStdDict[element]=100*np.std(np.delete(np.array(all_final_resis_dict[element]),finalIterIdx))/absTolMeanDict[element]
                    relTolFinalMeanDict[element]=np.mean(relTolDict[element][finalIterIdx])
                    relTolFinalStdDict[element]=100*np.std(relTolDict[element][finalIterIdx])/relTolFinalMeanDict[element]
                    relTolMeanDict[element]=np.mean(np.delete(relTolDict[element],finalIterIdx))
                    relTolStdDict[element]=100*np.std(np.delete(relTolDict[element],finalIterIdx))/relTolMeanDict[element]
                logger.info("%s absTol: %0.3e+-%0.2f%%  (%0.3e+-%0.2f%% on final iteration) relTol: %0.3e+-%0.2f%% (%0.3e+-%0.2f%% on final iteration)" % (element,absTolMeanDict[element],absTolStdDict[element],absTolFinalMeanDict[element],absTolFinalStdDict[element],relTolMeanDict[element],relTolStdDict[element],relTolFinalMeanDict[element],relTolFinalStdDict[element]))

        # Get unique values of nOuterCorrs and calculate mean tPerDt specific for each number of nOuterCorrs
        tPerDt_mean_pernCorrs={}
        unique_nOuterCorrs=np.unique(nOuterCorrs)
        for element in unique_nOuterCorrs:
            idx_pernCorrs=np.where(nOuterCorrs==element)
            mask_nCorr = np.zeros(len(nOuterCorrs), dtype=bool)
            mask_nCorr[idx_pernCorrs]=True
            mask_nCorr_noWrites=np.logical_xor(mask_nCorr,np.logical_and(mask_nCorr,mask))
            tPerDt_mean_pernCorrs[element]=np.mean(tPerDt[mask_nCorr_noWrites])
        # Calculate specific tPerDt for each writeTime or meancalc time
        tPerDt_restart=[]
        for element,iRestart in zip(np.array(nOuterCorrs)[mask_restart],range(len(np.array(nOuterCorrs)[mask_restart]))):
            tPerDt_restart.append(tPerDt_mean_pernCorrs[element])
        tPerDt_fObj=[]
        for element in np.array(nOuterCorrs)[mask_fobjs]:
            tPerDt_fObj.append(tPerDt_mean_pernCorrs[element])
        tPerDt_meancalc=[]
        for element in np.array(nOuterCorrs)[mask_meancalcAlone]:
            tPerDt_meancalc.append(tPerDt_mean_pernCorrs[element])

        # Calculate mean of writeTimes and meancalc
        tWrites_mean=0
        tWrites_fObj_mean=0
        tMeancalc_mean=0
        add_time_restart_mean=0
        add_time_fobj_mean=0
        add_time_meancalc_mean=0
        if any(mask_meancalcAlone):
            tMeancalc=tPerDt[mask_meancalcAlone]-tPerDt_meancalc
            tMeancalc_mean=np.mean(tMeancalc)
            tMeancalc_std=np.std(tMeancalc)
            add_time_meancalc=tMeancalc + clockdiff[mask_meancalcAlone]
            # Calculate average additional overall meancalc time
            add_time_meancalc_mean=np.mean(add_time_meancalc)
        if any(mask_write):
            tWrites=tPerDt[mask_restart]-tPerDt_restart
            tWrites_mean=np.mean(tWrites)
            tWrites_std=np.std(tWrites)
            add_time_restart=tWrites+clockdiff[mask_restart]-np.logical_and(mask_meancalc,mask_restart)[mask_restart].astype(int)*add_time_meancalc_mean
            add_time_restart_mean=np.mean(add_time_restart)
            if any(mask_fobjs):
                tWrites_fObj=tPerDt[mask_fobjs]-tPerDt_fObj
                tWrites_fObj_mean=np.mean(tWrites_fObj)
                tWrites_fObj_std=np.std(tWrites_fObj)
                add_time_fobj=tWrites_fObj+clockdiff[mask_fobjs]-np.logical_and(mask_meancalc,mask_fobjs)[mask_fobjs].astype(int)*add_time_meancalc_mean
                add_time_fobj_mean=np.mean(add_time_fobj)


        # Sum values for output
        overall_eff_raw=eff_base_mean+eff_clockdiff_mean
        overall_eff_raw_std = np.std(eff_base+eff_clockdiff_perDt)
        # Calculate average additional overall write time
        tWrites_overall=add_time_restart_mean+add_time_fobj_mean
        # Calculate normalised write time
        overall_eff_write=(nProc*tWrites_overall)/int(nCells)

        # Get names of present residuals
        resi_names=[*all_resis_dict]

        return {
            # ── Foreign-key stubs (pass IDs you already have, or None to create new) ──
            "campaign":                      None,   # int | Campaign dict
            "mesh_properties":               {"n_cells": int(nCells)},
            "solution_algorithm_settings":   {
                "n_outer_corr":     round(nOuterCorrsMean),
                "n_corr":           nCorrectors,
                "n_non_ortho_corr": nonOrthoCorr,
            },
            "hardware_config":               None,   # int | HardwareConfig dict
            "software":                      {
                "software_name":        executable,
                "version":              OFversion,
                # commit_hash and pressure_or_density must be filled externally
            },

            # ── linear_solver_settings: one entry per variable ────────────────────────
            "linear_solver_settings": {
                var: {"solver": solver_name}
                for var, solver_name in all_solvers_dict.items()
            },

            # ── Decomposition ─────────────────────────────────────────────────────────
            "num_of_sub_domains": nProc,
            "comment":            f"Case: {casename} | Host: {host} | Date: {date} {time} | "
                                f"OFversion: {OFversion} | turbModel: {turbModel} | "
                                f"fobjects: {fobjects}",

            # ── IO ────────────────────────────────────────────────────────────────────
            "io_write_interval":              float(writeInterval),
            "io_t_writes_mean":               float(tWrites_mean),
            "io_clockdiff_per_restart_write": float(clockdiff_perRestartWrite),
            "io_t_writes_fobj_mean":          float(tWrites_fObj_mean),
            "io_clockdiff_per_fobj_write":    float(clockdiff_perfObjWrite),
            "io_upcco_mean":                  float(upcco_mean),
            "io_add_time_meancalc_mean":      float(add_time_meancalc_mean),
            "io_fobjects":                    float(len(fobjects)),

            # ── Overhead ──────────────────────────────────────────────────────────────
            "overhead_exec_time_delta":  float(clockdiff_share_dt),
            "overhead_clock_time_delta": float(clockdiff_sum),

            # ── Runtime ───────────────────────────────────────────────────────────────
            "runtime_clock_time":       clockTime[-1],
            "runtime_tinit":            float(tinit),
            "runtime_t_per_dt_mean":    float(tPerDt_mean),
            "runtime_clockdiff_per_dt": float(clockdiff_perDt),

            # ── TimeStepping ──────────────────────────────────────────────────────────
            "time_stepping_size": float(timeStepSize),
            "time_stepping_time": simTime[-1],

            # ── Continuity errors (last values seen in log) ───────────────────────────
            "time_step_cont_errors_sum_local": None,  # not parsed – extend if needed
            "global_sum":                      None,
            "cumulative":                      None,

            # ── Residual measurements (one entry per variable) ────────────────────────
            "residual_measurements": [
                {
                    "variable":           var,
                    "avg_initial_residue": float(np.mean(vals)) if vals else None,
                    "avg_final_residue":  (
                        float(np.mean(all_final_resis_dict[var]))
                        if self.lin_tol and var in all_final_resis_dict
                        else None
                    ),
                }
                for var, vals in all_resis_dict.items()
            ],

            # ── Iteration measurements (one entry per variable) ───────────────────────
            "iterations": [
                {
                    "variable":          var,
                    "avg_lin_solv_it":   float(iters_p_mean) if var == "p" else 0.0,
                    "acc_linear_solv_it": float(sum(iters_p_list)) if var == "p" else 0.0,
                }
                for var in all_resis_dict
            ],
            "scheme_settings" : self.get_scheme_from_log()
        }
    
    def get_file_as_str(self) -> str:
        """Utility method to read a file and return its contents as a string."""
        with open(self.log_file_path, 'r') as f:
            return f.read()
    
    def get_n_cells_from_file(self) -> int:
        try:
            foundpath=glob.glob(self.log_file_path)
            # Handle standard or compressed file 
            if foundpath[0].endswith("gz"):
                isbinary=True
                f = gzip.open(foundpath[0], "rb")
            else:
                isbinary=False
                f = open(foundpath[0],"r",errors='ignore')
            for i in range(25):
                if isbinary:
                    text=f.readline().decode('ascii')
                else:
                    text=f.readline()
                matches = re.findall("nCells:(\d+)", text)
                if matches:
                    nCells=int(matches[0])
                    break
            f.close()
        except Exception as e:
            return None 
        return nCells
    
    def get_write_interval_from_file(self) -> int:
        try:
            with open(self.log_file_path,'r') as cfile:
                controldictstring=cfile.read()
                writeControl=re.search("writeControl\s+(\w+)", controldictstring).group(1)
                loadedwriteInterval=re.search("writeInterval\s+([-+]?(\d+([.,]\d*)?|[.,]\d+)([eE][-+]?\d+)?)", controldictstring).group(1)
                if writeControl=="timeStep":
                    return int(loadedwriteInterval)
                else:
                    dt=float(re.search("deltaT\s+([-+]?(\d+([.,]\d*)?|[.,]\d+)([eE][-+]?\d+)?)", controldictstring).group(1))
                    return round(float(loadedwriteInterval)/dt)
        except Exception as e:
            return None
