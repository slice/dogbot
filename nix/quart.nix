{ lib
, fetchFromGitHub
, buildPythonPackage
, pythonOlder

, aiofiles
, blinker
, click
, hypercorn
, hypothesis
, importlib-metadata
, itsdangerous
, jinja2
, markupsafe
, mock
, poetry-core
, pydata-sphinx-theme
, pytest-asyncio
, pytestCheckHook
, python-dotenv
, typing-extensions
, werkzeug
}:

buildPythonPackage rec {
  pname = "quart";
  version = "0.18.3";
  disabled = pythonOlder "3.7";
  format = "pyproject";

  src = fetchFromGitHub {
    owner = "pallets";
    repo = pname;
    rev = "b0676aa80487dcdf559f7169aba89a016e529c3b";
    sha256 = "sha256-aQM8kEhienBG+/zQQ8C/DKiDIMF3l9rq8HSAvg7wvLM=";
  };

  prePatch = ''
    substituteInPlace pyproject.toml \
        --replace "--no-cov-on-fail" ""
  '';

  propagatedBuildInputs = [
    aiofiles
    blinker
    click
    hypercorn
    importlib-metadata
    itsdangerous
    jinja2
    markupsafe
    pydata-sphinx-theme
    python-dotenv
    typing-extensions
    werkzeug
  ];

  checkInputs = [
    poetry-core

    hypothesis
    mock
    pytest-asyncio
    pytestCheckHook
  ];

  pythonImportsCheck = [ "quart" ];

  meta = with lib; {
    homepage = "https://quart.palletsprojects.com/en/latest/";
    description = "A Python ASGI web microframework with the same API as Flask";
    license = licenses.mit;
    maintainers = with maintainers; [ dgliwka oxzi ];
  };
}
