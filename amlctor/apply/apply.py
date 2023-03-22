from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from amlctor.core import StepSchema
from confs.configs import TEMPLATES_DIR, STEP_NAME_MAX, STEP_NAME_MIN, STEP_NAME_KEYWORDS
from amlctor.utils import get_settingspy_module, is_pipe
from amlctor import exceptions as exceptions
from amlctor import schemas





class StructureApply:
    jinva_env: Environment = Environment(loader=FileSystemLoader(f"{TEMPLATES_DIR}/apply/"))

    def __init__(self, path):
        """ path which contains settings directory """
        assert isinstance(path, Path) and path.is_dir(), f"incorrect dir: {path}"
        self.path = path
        

    def make_step_dirs(self):
        """ 
            Creates step dirs and files based on the `settings.py` file.
        """
        
        for step in self.settingspy['STEPS']:
            step_path = self.path / step.name
            step_path.mkdir(mode=0o770)                 # create dir for pipe step
            self.create_files(step, step_path)          # create files inside step dir


    def create_files(self, step: StepSchema, step_path: Path):
        script_name = self.settingspy['SCRIPT_MODULE_NAME']               # create script.py
        if not script_name.endswith('.py'):
                script_name = script_name + '.py'
        (step_path / script_name).touch(exist_ok=False)


        dataloader_name = self.settingspy['DATALOADER_MODULE_NAME']       # create data_loader.py 
        if not dataloader_name.endswith('.py'):
            dataloader_name = dataloader_name + '.py'

        content, keys = StructureApply.create_dataloader_content(step=step)
        with (step_path / dataloader_name).open(mode='w+') as dataloader:
            dataloader.write(content)

        aml_name = self.settingspy['AML_MODULE_NAME']                     # create aml.py
        if not aml_name.endswith('.py'):
                aml_name = aml_name + '.py'
        with (step_path / aml_name).open(mode='w+') as aml:
            aml_t = StructureApply.jinva_env.get_template('aml')
            content = aml_t.render(dataloader_name=dataloader_name, keys=keys)
            aml.write(content)



    @staticmethod
    def create_dataloader_content(step: StepSchema):
        """ Returns content for dataoaders.py and input names """

        def get_pandas_reader(filename: str):
            """ returns pandas reader method name for filename extention """          
            if filename.endswith('.parquet'):
                return "read_parquet()"
            elif filename.endswith(".csv"):
                return "read_csv()"
            elif filename.endswith(".xls") or filename.endswith(".xlsx"):
                return "read_excel()"
            elif filename.endswith(".json"):
                return "read_json()"
            else:
                raise ValueError(f"Unsupported file: {filename}. Supports: parquet, csv, excel, json")

        dataloader_t = StructureApply.jinva_env.get_template('data_loaders')

        res = {}
        data_list = step.input_data     # list of FileInput objects
        for data in data_list:
            if data.__class__.__name__ == 'FileInput':
                res[data.name] = [data.filename, get_pandas_reader(data.filename)]
            elif data.__class__.__name__ == 'PathInput':
                res[data.name] = [data.path, -1]    # pandas method for PathInput = -1
            
            else:
                ValueError(f"InternalError: Unsupported DataInput object: {type(data)}")
        
        content = dataloader_t.render(inputs=res)
        return content, list(res.keys())
    
        

    def start(self):
        self.settingspy = get_settingspy_module(self.path)
        self.pipe_name: str = self.path.name
        self.make_step_dirs()



class ApplyHandler:

    def __init__(self, path: Path):
        self.path = path
        self.check_path()


    def check_path(self):
        if not is_pipe(self.path):
            raise exceptions.PathHasNoPipelineException(path =      self.check_path, 
                                                        message =   schemas.PathHasNoPipelineSchema.message)
        

    def validate(self):
        MAX_LEN = 128
        settingspy = get_settingspy_module(self.path)
        steps = settingspy['STEPS']
        for step in steps:

            if not isinstance(step.name, str):
                raise exceptions.IncorrectTypeArgumentException(valid_type=str,
                                                                actually_is=type(name),
                                                                message=schemas.IncorrectArgumentTypeSchema.message)
            self.name = self.name.strip()
            name = self.name

            if not name.isidentifier():
                raise exceptions.IncorrectStepNameException(step_name = name,
                                                            message =   schemas.IncorrectStepNameSchema.IsNotIdentifier)
            elif len(name) < STEP_NAME_MIN:
                raise exceptions.IncorrectStepNameException(step_name = name,
                                                            message =   schemas.IncorrectStepNameSchema.LowMin)
            elif len(name) > STEP_NAME_MAX:
                raise exceptions.IncorrectStepNameException(step_name = name,
                                                            message =   schemas.IncorrectStepNameSchema.UpMax)
            elif name in STEP_NAME_KEYWORDS:
                raise exceptions.IncorrectStepNameException(step_name = name,
                                                            message =   schemas.IncorrectStepNameSchema.IsKeyWord)




    def start(self):
        StructureApply(path=self.path).start()      # start apply strukture builder

